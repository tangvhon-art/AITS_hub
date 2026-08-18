import logging
import json
import logging
from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.notification_service import notify_event

logger = logging.getLogger(__name__)


PERFORMANCE_ANALYSIS_SYSTEM_PROMPT = """你是一名资深性能测试工程师，拥有10年以上性能测试与调优经验。你的任务是根据提供的性能测试数据，生成一份专业、深入、数据准确的性能分析报告。

## 输出格式
直接输出 Markdown 格式文本，不要输出 JSON，不要输出代码块。

## 报告结构（必须包含以下6个二级标题，用 ## 开头）

## 一、整体性能评估
- 结合 RPS、平均响应时间、P95/P99、失败率综合评估系统整体性能
- 参考并发用户数和持续时间，判断系统在该负载下的表现
- 给出明确的性能等级（优秀/良好/一般/较差）

## 二、聚合报告分析
- 对比各接口的请求量占比、平均响应时间、错误率
- 找出最耗时和最不稳定的接口
- 分析标准差较大的接口是否存在性能波动

## 三、响应时间趋势分析
- 判断响应时间趋势是平稳、上升还是下降
- RPS 是否稳定，是否存在明显的性能拐点
- 失败请求是否集中在某个时间段

## 四、瓶颈识别
- 明确指出性能瓶颈所在（具体接口名称 + 具体指标）
- 区分是 CPU 密集、IO 密集还是外部依赖导致

## 五、根因分析与优化建议
- 针对每个瓶颈给出可能的根因
- 给出具体可执行的优化措施（缓存、SQL优化、连接池、扩容、代码优化等）

## 六、风险提示与后续建议
- 指出当前性能数据中需要关注的潜在风险
- 给出后续测试建议（增加并发、延长测试、资源监控等）

## 生成原则（最高优先级，必须严格遵守）
1. **数据绝对准确**：所有数值必须来自下方提供的测试数据，禁止编造、估算或推算任何数字
2. **整体指标优先**：引用整体性能时，必须使用"性能指标汇总"中的数值，不要使用各接口的数值
3. **接口分析用接口数据**：分析具体接口时，才使用"各接口统计"中的数据
4. **禁止重复**：不要重复输出相同内容，不要输出无意义的重复字符或符号
5. **语言简洁专业**：每个要点不超过2句话，总字数控制在1000字以内
6. **单位规范**：响应时间用"毫秒"，吞吐量用"请求/秒"，不要用"ms"或"RPS"缩写
7. **如果某项数据为0或空**，如实说明，不要编造
8. **所有内容使用中文**"""


@celery_app.task(bind=True, name="run_performance_test", max_retries=0)
def run_performance_test_task(
    self,
    run_id: int,
    test_config: dict,
    targets: list,
    headers: dict,
    test_data: list = None,
):
    """异步执行性能测试（多接口）

    targets: [{method, url, name, weight, body}]
    """
    db = SessionLocal()
    try:
        from app.services.performance_runner import PerformanceRunner
        runner = PerformanceRunner(db)
        result = runner.run(
            run_id=run_id,
            test_config=test_config,
            targets=targets,
            headers=headers,
            test_data=test_data,
        )
        logger.info(f"性能测试执行完成: run_id={run_id}, status={result.get('status')}")

        # 发送性能测试完成通知
        try:
            from app.models.performance_test import PerformanceTest, PerformanceTestRun
            run = db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
            if run:
                test = db.query(PerformanceTest).filter(PerformanceTest.id == run.test_id).first()
                metrics = run.metrics or {}
                summary = metrics.get("summary", {}) if isinstance(metrics, dict) else {}
                duration_s = 0
                if run.started_at and run.finished_at:
                    duration_s = round((run.finished_at - run.started_at).total_seconds(), 2)
                notify_event(
                    test.project_id if test else None,
                    "performance.completed",
                    {
                        "test_id": run.test_id,
                        "run_id": run.id,
                        "test_name": test.name if test else "性能测试",
                        "virtual_users": test_config.get("virtual_users", test_config.get("vus", 0)),
                        "duration": test_config.get("duration", test_config.get("hold_seconds", duration_s)),
                        "total_requests": summary.get("total_requests", metrics.get("total_requests", 0)),
                        "rps": summary.get("rps", metrics.get("rps", 0)),
                        "avg_response_time": summary.get("avg_response_time", metrics.get("avg_response_time", 0)),
                        "p95_response_time": summary.get("p95_response_time", metrics.get("p95_response_time", 0)),
                        "p99_response_time": summary.get("p99_response_time", metrics.get("p99_response_time", 0)),
                        "failure_rate": summary.get("failure_rate", metrics.get("failure_rate", 0)),
                    },
                    triggered_by=getattr(run, "triggered_by", None),
                )
        except Exception as notify_e:
            logger.warning(f"发送性能测试通知失败（不影响业务）: {notify_e}")

        return result
    except Exception as e:
        logger.error(f"性能测试执行失败: run_id={run_id}, error={e}", exc_info=True)
        try:
            from app.models.performance_test import PerformanceTest, PerformanceTestRun
            from app.core.timezone import china_now_naive
            run = db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
            if run:
                run.status = "failed"
                run.finished_at = china_now_naive()
                run.error_summary = {"error": str(e)[:500]}
                test = db.query(PerformanceTest).filter(PerformanceTest.id == run.test_id).first()
                if test:
                    test.status = "failed"
                db.commit()
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}
    finally:
        # 安全防护：确保测试状态不卡在 running
        try:
            from app.models.performance_test import PerformanceTest, PerformanceTestRun
            run = db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
            if run and run.test_id:
                test = db.query(PerformanceTest).filter(PerformanceTest.id == run.test_id).first()
                if test and test.status == "running":
                    running_count = db.query(PerformanceTestRun).filter(
                        PerformanceTestRun.test_id == test.id,
                        PerformanceTestRun.status == "running",
                    ).count()
                    if running_count == 0:
                        test.status = "completed"
                        db.commit()
                        logger.info(f"安全防护：测试 #{test.id} 状态从 running 修正为 completed")
        except Exception:
            pass
        db.close()


@celery_app.task(bind=True, name="analyze_performance", max_retries=0)
def analyze_performance_task(
    self,
    run_id: int,
    user_id: int = None,
    llm_config_id: int = None,
    prompt_id: int = None,
):
    """异步分析性能测试结果，生成性能报告"""
    db = SessionLocal()
    try:
        from app.models.performance_test import PerformanceTestRun, PerformanceTest
        from app.models.report import TestReport
        from app.core.timezone import china_now_naive

        run = db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
        if not run:
            return {"status": "failed", "error": "执行记录不存在"}

        test = db.query(PerformanceTest).filter(PerformanceTest.id == run.test_id).first()

        config = run.config_snapshot or {}
        users = config.get('users', 0)
        duration = config.get('duration', 0)

        # ========== 1. 性能指标汇总（整体，纯文本，避免 JSON 混淆） ==========
        metrics_text = f"""总请求数：{run.total_requests}
失败请求数：{run.total_failures}
失败率：{run.failure_rate}%
成功率：{round(100 - run.failure_rate, 2)}%
吞吐量：{run.requests_per_second} 请求/秒
平均响应时间：{run.avg_response_time} 毫秒
最小响应时间：{run.min_response_time} 毫秒
最大响应时间：{run.max_response_time} 毫秒
P50响应时间：{run.p50_response_time} 毫秒
P95响应时间：{run.p95_response_time} 毫秒
P99响应时间：{run.p99_response_time} 毫秒"""

        # ========== 2. 各接口统计（取请求量最多的前5个，纯文本表格） ==========
        endpoint_stats = run.endpoint_stats or []
        # 按请求量排序，取前5
        sorted_endpoints = sorted(endpoint_stats, key=lambda x: x.get('samples', 0), reverse=True)[:5]
        if sorted_endpoints:
            endpoint_lines = ["| 接口 | 请求数 | 平均响应(ms) | P95(ms) | 错误率 | 吞吐量(r/s) |",
                              "|------|--------|-------------|---------|--------|------------|"]
            for ep in sorted_endpoints:
                endpoint_lines.append(
                    f"| {ep.get('label','?')} | {ep.get('samples',0)} | {ep.get('average',0)} | "
                    f"{ep.get('p95',0)} | {ep.get('error_pct',0)}% | {ep.get('throughput',0)} |"
                )
            endpoint_text = "\n".join(endpoint_lines)
        else:
            endpoint_text = "无各接口统计数据"

        # ========== 3. 响应时间趋势（纯文本描述） ==========
        trend_text = "无趋势数据"
        raw_history = run.stats_history
        if raw_history:
            agg_list = raw_history.get("aggregate", []) if isinstance(raw_history, dict) else (raw_history if isinstance(raw_history, list) else [])
            if agg_list and len(agg_list) > 1:
                rps_vals = [h.get("rps", 0) for h in agg_list if h.get("rps") is not None]
                avg_vals = [h.get("average_response_time", h.get("avg", 0)) for h in agg_list if h.get("average_response_time", h.get("avg")) is not None]
                p95_vals = [h.get("p95", 0) for h in agg_list if h.get("p95") is not None]
                fail_vals = [h.get("failures", 0) for h in agg_list if h.get("failures") is not None]

                avg_trend = "平稳"
                if avg_vals and avg_vals[-1] > avg_vals[0] * 1.2:
                    avg_trend = "上升（响应时间逐渐变长，可能存在性能退化）"
                elif avg_vals and avg_vals[-1] < avg_vals[0] * 0.8:
                    avg_trend = "下降（响应时间逐渐变短）"

                rps_stable = "稳定"
                if rps_vals and (max(rps_vals) - min(rps_vals)) / (max(rps_vals) or 1) > 0.3:
                    rps_stable = "波动较大"

                fail_concentrated = "均匀分布"
                if fail_vals and sum(fail_vals[len(fail_vals)//2:]) > sum(fail_vals[:len(fail_vals)//2]) * 2:
                    fail_concentrated = "集中在测试后半段"

                trend_text = f"""数据采样点数：{len(agg_list)}
吞吐量趋势：起始 {rps_vals[0] if rps_vals else 0} → 结束 {rps_vals[-1] if rps_vals else 0}，峰值 {max(rps_vals) if rps_vals else 0}，谷值 {min(rps_vals) if rps_vals else 0}，整体{rps_stable}
平均响应时间趋势：起始 {avg_vals[0] if avg_vals else 0}ms → 结束 {avg_vals[-1] if avg_vals else 0}ms，峰值 {max(avg_vals) if avg_vals else 0}ms，趋势{avg_trend}
P95响应时间：起始 {p95_vals[0] if p95_vals else 0}ms → 结束 {p95_vals[-1] if p95_vals else 0}ms，峰值 {max(p95_vals) if p95_vals else 0}ms
失败请求分布：{fail_concentrated}，总失败数 {sum(fail_vals) if fail_vals else 0}"""

        # ========== 4. 错误汇总 ==========
        error_summary = run.error_summary or {}
        if error_summary:
            error_lines = [f"- {k}: {v}" for k, v in list(error_summary.items())[:10]]
            error_text = "\n".join(error_lines)
        else:
            error_text = "无错误记录"

        # ========== 构建 HUMAN 消息（纯文本数据，不用 JSON 堆砌） ==========
        human_content = f"""## 测试基本信息
测试名称：{test.name if test else '未知'}
执行ID：{run.id}
并发用户数：{users}
持续时间：{duration}秒

## 性能指标汇总（整体数据，分析整体性能时必须使用这些数值）
{metrics_text}

## 各接口统计（请求量前5的接口，分析具体接口时使用）
{endpoint_text}

## 响应时间趋势
{trend_text}

## 错误汇总
{error_text}

请根据以上数据生成性能分析报告。"""

        # 调用 LLM
        from app.agents.llm_factory import llm_factory
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = None
        if llm_config_id:
            from app.models.llm_config import LLMConfig
            cfg = db.query(LLMConfig).filter(LLMConfig.id == llm_config_id, LLMConfig.is_deleted == False).first()
            if cfg:
                llm = llm_factory.get_llm_from_config({
                    "provider": cfg.provider, "model_name": cfg.model_name,
                    "base_url": cfg.base_url, "api_key": cfg.api_key,
                    "max_tokens": cfg.max_tokens or 4096,
                    "temperature": cfg.temperature if cfg.temperature is not None else 0.3,
                    "streaming": False,
                })
        if not llm:
            llm = llm_factory.get_default_llm(db)

        messages = [
            SystemMessage(content=PERFORMANCE_ANALYSIS_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        response = llm.invoke(messages)
        analysis_content = response.content if hasattr(response, 'content') else str(response)

        # 内容清洗：去除 LLM 异常输出
        import re
        # 去除连续5个以上的引号、括号、ms等重复模式
        analysis_content = re.sub(r'["\u201c\u201d]{5,}', '', analysis_content)
        analysis_content = re.sub(r'[()]{5,}', '', analysis_content)
        analysis_content = re.sub(r'(ms\s*){5,}', '', analysis_content)
        analysis_content = re.sub(r'(毫秒\s*){5,}', '', analysis_content)
        # 去除连续3个以上的逗号
        analysis_content = re.sub(r',{3,}', '，', analysis_content)
        # 去除连续3个以上的空行
        analysis_content = re.sub(r'\n{4,}', '\n\n\n', analysis_content)
        # 截断过长内容
        if len(analysis_content) > 6000:
            analysis_content = analysis_content[:6000] + '\n\n...（内容已截断）'

        # 创建性能报告
        report = TestReport(
            project_id=run.project_id,
            title=f"性能分析报告 - {test.name if test else '测试'} #{run.id}",
            report_type="performance",
            content=analysis_content,
            summary={
                "run_id": run.id,
                "test_id": run.test_id,
                "total_requests": run.total_requests,
                "failure_rate": run.failure_rate,
                "avg_response_time": run.avg_response_time,
                "p95_response_time": run.p95_response_time,
                "rps": run.requests_per_second,
            },
            created_by=user_id,
            status="completed",
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        logger.info(f"性能分析报告已生成: report_id={report.id}, run_id={run_id}")

        # 发送通知
        try:
            notify_event(
                run.project_id,
                "performance.analyzed",
                {
                    "run_id": run_id,
                    "report_id": report.id,
                    "test_name": test.name if test else "性能测试",
                    "report_title": report.title,
                },
                triggered_by=user_id,
            )
        except Exception as notify_e:
            logger.warning(f"发送性能分析通知失败: {notify_e}")

        return {"status": "completed", "report_id": report.id}

    except Exception as e:
        logger.error(f"性能分析失败: run_id={run_id}, error={e}", exc_info=True)
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
