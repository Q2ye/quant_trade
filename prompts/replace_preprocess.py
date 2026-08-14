import re, ast

path = 'quant_server/modules/data/services/sync_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

applied = 0

# Each fix: (unique_old_start, old_full_block, new_code)
# We match unique start strings and replace up to the next line after the block

fixes = [
    # _sync_financial_indicator: nan + ann_date/end_date + known_cols -> try
    ('\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\ttry:',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'), known_cols=known_cols)\n\t\t\t\t\ttry:'),

    # _sync_audit_opinion: same pattern, deeper indent
    ('\t\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'), known_cols=known_cols)\n\t\t\t\t\t\t\ttry:'),

    # _sync_business_income: nan + end_date + known_cols
    ('\t\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'end_date\',), known_cols=known_cols)\n\t\t\t\t\t\t\ttry:'),

    # _sync_forecast: nan + ann_date/end_date
    ('\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'))\n\t\t\t\t\t\ttry:'),

    # _sync_express: same as forecast
    ('\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\ttry:',
     None),  # already handled by forecast pattern

    # _sync_dividend: nan + ann_date
    ('\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\',))\n\t\t\t\t\t\ttry:'),

    # _sync_suspend_info: nan + trade_date
    ('\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\tif item.get(\'trade_date\'): item[\'trade_date\'] = _convert_to_date(item[\'trade_date\'])\n\t\t\t\t\t\ttry:',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'trade_date\',))\n\t\t\t\t\ttry:'),

    # _sync_etf_share: nan + trade_date (deeper indent)
    ('\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'trade_date\'): item[\'trade_date\'] = _convert_to_date(item[\'trade_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'trade_date\',))\n\t\t\t\t\t\ttry:'),

    # _sync_index_basic: nan + list_date/base_date/exp_date
    ('\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t# 转换所有日期字段（Tushare 返回 \"19901219\" 格式字符串）\n\t\t\t\t\t\tfor date_field in (\'list_date\', \'base_date\', \'exp_date\'):\n\t\t\t\t\t\t\tif item.get(date_field):\n\t\t\t\t\t\t\t\titem[date_field] = _convert_to_date(item[date_field])\n\t\t\t\t\t\texisting = await self.index_basic_repo.get_by(ts_code=item[\"ts_code\"])',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'list_date\', \'base_date\', \'exp_date\'))\n\t\t\t\t\texisting = await self.index_basic_repo.get_by(ts_code=item[\"ts_code\"])'),

    # _sync_etf_index: nan + pub_date
    ('\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\tif item.get(\'pub_date\'):\n\t\t\t\t\t\t\titem[\'pub_date\'] = _convert_to_date(item[\'pub_date\'])\n\t\t\t\t\t\ttry:',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'pub_date\',))\n\t\t\t\t\t\ttry:'),

    # _sync_stock_company: nan + setup_date
    ('\t\t\t\tfor item in data:\n\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\tif \'setup_date\' in item and item[\'setup_date\']:\n\t\t\t\t\t\titem[\'setup_date\'] = _convert_to_date(item[\'setup_date\'])\n\t\t\t\t\texisting = await self.company_repo.get_by(ts_code=item[\"ts_code\"])',
     '\t\t\t\t_preprocess_records(data, date_fields=(\'setup_date\',))\n\t\t\t\t\texisting = await self.company_repo.get_by(ts_code=item[\"ts_code\"])'),

    # _sync_st_list: nan + start_date -> trade_date + name check
    ('\t\t\t\tfor item in data:\n\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\tif \'start_date\' in item and item[\'start_date\']:\n\t\t\t\t\t\titem[\'trade_date\'] = _convert_to_date(item[\'start_date\'])\n\t\t\t\t\tname = item.get(\'name\',\'\')',
     '\t\t\t\t_preprocess_records(data, date_fields=(\'start_date\',))\n\t\t\t\t\tfor item in data:\n\t\t\t\t\t\tif item.get(\'start_date\'): item[\'trade_date\'] = item[\'start_date\']\n\t\t\t\t\tname = item.get(\'name\',\'\')'),

    # _sync_financial_statement: report_type + dates + known_cols
    ('\t\t\t\tfor item in data:\n\t\t\t\t\titem[\"report_type\"] = report_type\n\t\t\t\t\titem[\'ann_date\'] = _convert_to_datetime(item.get(\'ann_date\'))\n\t\t\t\t\titem[\'end_date\'] = _convert_to_datetime(item.get(\'end_date\'))\n\t\t\t\t\tif item.get(\'f_ann_date\') and isinstance(item[\'f_ann_date\'], str):\n\t\t\t\t\t\titem[\'f_ann_date\'] = _convert_to_datetime(item[\'f_ann_date\'])\n\t\t\t\t\t# 过滤 Tushare 返回但 ORM 模型中不存在的字段\n\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\n\t\t\t\t\texisting = await self.financial_statement_repo.get_by_unique(',
     '\t\t\t\tfor item in data:\n\t\t\t\t\titem[\"report_type\"] = report_type\n\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\', \'f_ann_date\'), known_cols=known_cols)\n\n\t\t\t\t\texisting = await self.financial_statement_repo.get_by_unique('),

    # _sync_stk_managers: nan + ts_code + create
    ('\t\t\t\t\tfor item in data: item = _clean_nan_values(item); item[\'ts_code\'] = ts_code; await self.manager_repo.create(item); records_added += 1',
     '\t\t\t\t\t_preprocess_records(data)\n\t\t\t\t\tfor item in data: item[\'ts_code\'] = ts_code; await self.manager_repo.create(item); records_added += 1'),

    # _sync_stk_rewards: same pattern as managers
    ('\t\t\t\t\tfor item in data: item = _clean_nan_values(item); item[\'ts_code\'] = ts_code; await self.reward_repo.create(item); records_added += 1',
     '\t\t\t\t\t_preprocess_records(data)\n\t\t\t\t\tfor item in data: item[\'ts_code\'] = ts_code; await self.reward_repo.create(item); records_added += 1'),
]

for i, (old, new) in enumerate(fixes):
    if new is None:
        continue
    if old in content:
        content = content.replace(old, new)
        applied += 1
    else:
        print(f'#{i+1} NOT FOUND: {old[:60]}...')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

# Verify syntax
try:
    ast.parse(content)
    print(f'\nApplied {applied} fixes. Syntax OK.')
except SyntaxError as e:
    print(f'\nApplied {applied} fixes. SYNTAX ERROR at line {e.lineno}: {e.msg}')
    # Show the error line
    lines = content.split('\n')
    if e.lineno:
        for offset in range(-2, 3):
            i = e.lineno - 1 + offset
            if 0 <= i < len(lines):
                print(f'  {i+1}: {repr(lines[i][:120])}')
