#!/usr/bin/env python3
"""表格层批量迁移：a-table→DataTable / a-popconfirm删除→统一confirmDelete / CRUD a-modal→FormModal。
用法: python3 migrate_table.py <view文件>...
"""
import re, sys

def convert(path: str) -> str:
    s = open(path, encoding='utf-8').read()
    log = []

    # ── 1. a-table → DataTable ──
    if '<a-table' in s and '<DataTable' not in s:
        # 逐块替换 <a-table ...> 与 </a-table>
        def repl_table(m):
            tag = m.group(0)
            # 属性映射
            tag = re.sub(r':pagination="pagination"', ':page="pagination.current"\n        :page-size="pagination.pageSize"\n        :total="pagination.total"', tag)
            tag = re.sub(r':pagination="pagination\.value"', ':page="pagination.current"\n        :page-size="pagination.pageSize"\n        :total="pagination.total"', tag)
            tag = re.sub(r':pagination="paginationConfig"', ':page="paginationConfig.current"\n        :page-size="paginationConfig.pageSize"\n        :total="paginationConfig.total"', tag)
            # 移除分页字面量（不分页表格）
            tag = re.sub(r':pagination="false"\s*\n', '', tag)
            # 字面量分页对象（如 { pageSize: 20 }）→ 移除（DataTable 自带分页，total 由数据长度决定）
            tag = re.sub(r':pagination="\{[^}]*\}"\s*\n', '', tag)
            tag = tag.replace('<a-table', '<DataTable', 1)
            return tag
        s = re.sub(r'<a-table\b[^>]*>', repl_table, s)
        s = s.replace('</a-table>', '</DataTable>')
        log.append('DataTable ✓')

    # ── 2. a-popconfirm 删除 → confirmDelete(record, fn) ──
    if '<a-popconfirm' in s:
        def repl_pop(m):
            block = m.group(0)
            cm = re.search(r'@confirm="([^"]+)"', block)
            if not cm:
                return block
            fn = cm.group(1).strip()
            # 按钮标签（删除/移除/停用等）
            bm = re.search(r'<a-button([^>]*)>([^<]+)</a-button>', block)
            if not bm:
                return block
            attrs, label = bm.group(1), bm.group(2).strip()
            # 去掉按钮上可能重复的 @click
            attrs = re.sub(r'\s*@click="[^"]*"', '', attrs)
            return f'<a-button{attrs} @click="confirmDelete(record, () => {fn})">{label}</a-button>'
        s = re.sub(r'<a-popconfirm[^>]*>[\s\S]*?</a-popconfirm>', repl_pop, s)
        log.append('popconfirm→confirmDelete ✓')

    # ── 3. CRUD a-modal → FormModal ──
    # 仅处理含 @ok 或 :confirm-loading 的 modal（新建/编辑类），跳过 :footer="null" 与自定义 footer
    def repl_modal(m):
        block = m.group(0)
        if ':footer="null"' in block or ':footer="false"' in block or '#footer' in block or '@ok' not in block:
            return block
        # 提取属性
        open_m = re.search(r'v-model:open="(\w+)"', block)
        visible_name = open_m.group(1) if open_m else 'modalVisible'
        title_m = re.search(r'title="([^"]*)"', block)
        title = title_m.group(1) if title_m else ''
        ok_m = re.search(r'@ok="(\w+)"', block)
        ok_fn = ok_m.group(1) if ok_m else 'submit'
        loading_m = re.search(r':confirm-loading="(\w+)"', block)
        loading = loading_m.group(1) if loading_m else 'modalLoading'
        cancel_m = re.search(r'@cancel="(\w+)"', block)
        cancel = cancel_m.group(1) if cancel_m else ''
        width_m = re.search(r'width="([^"]+)"', block)
        width = width_m.group(1) if width_m else '600'
        # 移除 a-form 包裹（FormModal 自带）
        inner = block
        inner = re.sub(r'<a-form[^>]*>\s*', '', inner, count=1)
        inner = re.sub(r'\s*</a-form>\s*(?=</a-modal>)', '', inner)
        inner = re.sub(r'</a-modal>', '', inner)
        inner = re.sub(r'<a-modal\b[^>]*>', '', inner, count=1)
        # 构造 FormModal
        attrs = f'v-model:visible="{visible_name}"\n      title="{title}"\n      :loading="{loading}"\n      width="{width}"'
        if cancel:
            attrs += f'\n      @cancel="{cancel}"'
        new_block = f'<FormModal\n      {attrs}\n      @ok="{ok_fn}"\n    >\n      {inner.strip()}\n    </FormModal>'
        return new_block
    s = re.sub(r'<a-modal\b[^>]*>[\s\S]*?</a-modal>', repl_modal, s)
    log.append('FormModal ✓')

    # ── 4. import 公共组件 ──
    need = []
    if '<DataTable' in s and "from '@/components/DataTable.vue'" not in s: need.append("DataTable")
    if '<FormModal' in s and "from '@/components/FormModal.vue'" not in s: need.append("FormModal")
    if 'confirmDelete(' in s:
        need.append("useConfirmDelete")
    if need:
        add = ''
        if 'DataTable' in need: add += "import DataTable from '@/components/DataTable.vue'\n"
        if 'FormModal' in need: add += "import FormModal from '@/components/FormModal.vue'\n"
        if 'useConfirmDelete' in need: add += "import { useConfirmDelete } from '@/composables/useConfirmDelete'\n"
        lines = s.split('\n')
        # 找最后一个单行 import（跳过多行 import 块）
        idx = -1
        i = 0
        while i < len(lines):
            l = lines[i]
            if l.startswith('import ') and not l.rstrip().endswith('{'):
                idx = i
            i += 1
        if idx >= 0:
            lines.insert(idx + 1, add.rstrip('\n'))
            s = '\n'.join(lines)
            log.append('imports ✓')

    # ── 5. 若用了 confirmDelete，添加解构（若页面尚未有）──
    if 'confirmDelete(' in s and 'const { confirmDelete }' not in s and 'confirmDelete,' not in s:
        # 在 <script setup> 中首个 const 前插入解构（简单方案：追加到文件尾部可能不合法，插到 script 开头 import 之后）
        lines = s.split('\n')
        ins = -1
        for i, l in enumerate(lines):
            if l.startswith('import ') and not l.rstrip().endswith('{'):
                ins = i
        if ins >= 0:
            lines.insert(ins + 1, "const { confirmDelete } = useConfirmDelete('数据')")
            s = '\n'.join(lines)
            log.append('useConfirmDelete 解构 ✓')

    if s != open(path, encoding='utf-8').read():
        open(path, 'w', encoding='utf-8').write(s)
    return '; '.join(log) if log else '未变化'

if __name__ == '__main__':
    for p in sys.argv[1:]:
        try:
            print(f'{p}: {convert(p)}')
        except Exception as e:
            print(f'{p}: ERROR {e}')
