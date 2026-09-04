#!/usr/bin/env python3
"""公共化批量迁移转换器：处理 头部→PageHeader / 筛选区→SearchBar / 删除→Modal.confirm 机械替换。
用法: python3 migrate_tool.py <view文件>...
"""
import re, sys

def convert(path: str) -> tuple[bool, str]:
    s = open(path, encoding='utf-8').read()
    orig = s
    log = []

    # ── 1. 头部 → PageHeader ──
    if '<PageHeader' not in s:
        m = re.search(r'<div class="page-header">([\s\S]*?)</div>\s*(?=<div class="filter-bar">|<a-table|<a-spin|<a-card|<!--)', s)
        if not m:
            # 放宽：到模板中下一个 div 前（通常 header 后是 filter-bar 或空行）
            m = re.search(r'<div class="page-header">([\s\S]*?)\n\s*(?:<div class="filter-bar">|</template>)', s)
        if m:
            block = m.group(1)
            tm = re.search(r'<h2>([^<]+)</h2>', block)
            if tm:
                title = tm.group(1).strip()
                # 按钮区：去掉 h2，保留其余（可能含 header-actions 包裹）
                btns = block.replace(tm.group(0), '')
                btns = re.sub(r'<div class="header-actions">\s*', '', btns)
                btns = re.sub(r'\s*</div>\s*$', '', btns)
                # 若整块被 header-actions 包住（上面替换后多余 </div>），清理多余包裹
                if btns.count('<div') > btns.count('</div>'):
                    btns = re.sub(r'^\s*<div[^>]*>', '', btns)
                btns = btns.strip()
                new_header = f'<PageHeader title="{title}">\n  <template #extra>\n    {btns}\n  </template>\n</PageHeader>'
                s = s.replace(m.group(0), new_header, 1)
                log.append('PageHeader ✓')

    # ── 2. 筛选区 → SearchBar ──
    if '<SearchBar' not in s:
        fm = re.search(r'<div class="filter-bar">([\s\S]*?)</div>\s*(?=<a-table|<a-spin|<a-card|<!--)', s)
        if fm:
            inner = fm.group(1)
            inner2 = re.sub(r'<a-button[^>]*>\s*<template #icon>[\s\S]*?</template>\s*查询\s*</a-button>', '', inner)
            inner2 = re.sub(r'<a-button[^>]*>\s*<template #icon>[\s\S]*?</template>\s*重置\s*</a-button>', '', inner2)
            inner2 = re.sub(r'<a-button[^>]*>\s*查询\s*</a-button>', '', inner2)
            inner2 = re.sub(r'<a-button[^>]*>\s*重置\s*</a-button>', '', inner2)
            # 也可能查询/重置按钮带 :loading 或不同写法
            inner2 = re.sub(r'<a-button[^>]*type="primary"[^>]*>查询</a-button>', '', inner2)
            inner2 = re.sub(r'<a-button[^>]*>重置</a-button>', '', inner2)
            inner2 = re.sub(r'\n\s*\n', '\n', inner2).strip()
            new_bar = f'<SearchBar @search="handleSearch" @reset="handleReset">\n  <a-form layout="inline">\n    {inner2}\n  </a-form>\n</SearchBar>'
            s = s.replace(fm.group(0), new_bar, 1)
            log.append('SearchBar ✓')

    # ── 3. import 公共组件（若已使用）──
    if '<PageHeader' in s and "from '@/components/PageHeader.vue'" not in s:
        comp_imports = ""
        if '<PageHeader' in s: comp_imports += "import PageHeader from '@/components/PageHeader.vue'\n"
        if '<SearchBar' in s: comp_imports += "import SearchBar from '@/components/SearchBar.vue'\n"
        lines = s.split('\n')
        idx = -1
        for i, l in enumerate(lines):
            if l.startswith('import ') and i > idx:
                idx = i
        if idx >= 0:
            lines.insert(idx + 1, comp_imports.rstrip('\n'))
            s = '\n'.join(lines)
            log.append('imports ✓')

    if s != orig:
        open(path, 'w', encoding='utf-8').write(s)
        return True, '; '.join(log)
    return False, '未变化'

if __name__ == '__main__':
    for p in sys.argv[1:]:
        try:
            ok, msg = convert(p)
            print(f'{p}: {msg}')
        except Exception as e:
            print(f'{p}: ERROR {e}')
