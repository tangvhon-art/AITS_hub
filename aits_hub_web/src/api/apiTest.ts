/**
 * 接口测试 API 统一入口（barrel re-export）
 *
 * 已按资源拆分为独立模块：
 * - apiModules.ts       目录管理
 * - apiDefinitions.ts   接口定义
 * - apiDebug.ts         接口调试
 * - apiCaseTests.ts     测试用例
 * - apiScenarioTests.ts 场景编排
 * - apiExecutionRecords.ts 执行记录
 * - apiMockService.ts   Mock 服务
 * - apiImportService.ts 接口导入
 * - mockData.ts         Mock 数据生成器
 *
 * 注意：LLM 配置请从 '@/api/llm' 导入，Chat 请从 '@/api/chat' 导入，
 * 环境管理请从 '@/api/environments' 导入。
 */
export type { ApiModule } from './apiModules'
export { apiModulesApi } from './apiModules'

export type { ApiDefinition } from './apiDefinitions'
export { apiDefinitionsApi } from './apiDefinitions'

export { apiDebugApi } from './apiDebug'

export type { ApiTestCase, ApiCaseAssertion } from './apiCaseTests'
export { apiCasesApi } from './apiCaseTests'

export type { ApiScenario, ApiScenarioStep } from './apiScenarioTests'
export { apiScenariosApi } from './apiScenarioTests'

export type { ApiExecution, ApiExecutionResult } from './apiExecutionRecords'
export { apiExecutionsApi } from './apiExecutionRecords'

export type { ApiMockExpectation } from './apiMockService'
export { apiMockApi } from './apiMockService'

export { apiImportApi } from './apiImportService'

export type { MockFunction } from './mockData'
export { mockDataApi } from './mockData'

export type { PaginatedResponse } from './types'
