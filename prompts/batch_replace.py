"""Apply _preprocess_records to all 15 methods."""
import ast, re

path = 'quant_server/modules/data/services/sync_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

fixes = [
    # 1. _sync_etf_basic (pub_date)
    ('1961_etf_basic',
     '\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\tif item.get(\'pub_date\'):\n\t\t\t\t\t\t\titem[\'pub_date\'] = _convert_to_date(item[\'pub_date\'])\n\t\t\t\t\t\ttry:',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'pub_date\',))\n\t\t\t\t\tfor item in data:\n\t\t\t\t\t\ttry:'),

    # 2. _sync_stock_company (setup_date)
    ('2804_stock_company',
     '\t\t\t\tfor item in data:\n\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\tif \'setup_date\' in item and item[\'setup_date\']:\n\t\t\t\t\t\titem[\'setup_date\'] = _convert_to_date(item[\'setup_date\'])\n\t\t\t\t\texisting = await self.company_repo.get_by(ts_code=item["ts_code"])',
     '\t\t\t\t_preprocess_records(data, date_fields=(\'setup_date\',))\n\t\t\t\tfor item in data:\n\t\t\t\t\texisting = await self.company_repo.get_by(ts_code=item["ts_code"])'),

    # 3. _sync_st_list (start_date -> trade_date)
    ('2859_st_list',
     '\t\t\t\tfor item in data:\n\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\tif \'start_date\' in item and item[\'start_date\']:\n\t\t\t\t\t\titem[\'trade_date\'] = _convert_to_date(item[\'start_date\'])\n\t\t\t\t\tname = item.get(\'name\',\'\')',
     '\t\t\t\t_preprocess_records(data, date_fields=(\'start_date\',))\n\t\t\t\tfor item in data:\n\t\t\t\t\tif item.get(\'start_date\'): item[\'trade_date\'] = item[\'start_date\']\n\t\t\t\t\tname = item.get(\'name\',\'\')'),

    # 4. _sync_stk_managers (nan only)
    ('2928_managers',
     '\t\t\t\t\tfor item in data: item = _clean_nan_values(item); item[\'ts_code\'] = ts_code; await self.manager_repo.create(item); records_added += 1',
     '\t\t\t\t\t_preprocess_records(data)\n\t\t\t\t\tfor item in data: item[\'ts_code\'] = ts_code; await self.manager_repo.create(item); records_added += 1'),

    # 5. _sync_stk_rewards (nan only)
    ('2986_rewards',
     '\t\t\t\t\tfor item in data: item = _clean_nan_values(item); item[\'ts_code\'] = ts_code; await self.reward_repo.create(item); records_added += 1',
     '\t\t\t\t\t_preprocess_records(data)\n\t\t\t\t\tfor item in data: item[\'ts_code\'] = ts_code; await self.reward_repo.create(item); records_added += 1'),

    # 6. _sync_index_basic (3 date fields)
    ('3169_index_basic',
     '\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t# 转换所有日期字段（Tushare 返回 "19901219" 格式字符串）\n\t\t\t\t\t\tfor date_field in (\'list_date\', \'base_date\', \'exp_date\'):\n\t\t\t\t\t\t\tif item.get(date_field):\n\t\t\t\t\t\t\t\titem[date_field] = _convert_to_date(item[date_field])\n\t\t\t\t\t\texisting = await self.index_basic_repo.get_by(ts_code=item["ts_code"])',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'list_date\', \'base_date\', \'exp_date\'))\n\t\t\t\t\tfor item in data:\n\t\t\t\t\t\texisting = await self.index_basic_repo.get_by(ts_code=item["ts_code"])'),

    # 7. _sync_suspend_info (trade_date)
    ('3380_suspend_info',
     '\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\tif item.get(\'trade_date\'): item[\'trade_date\'] = _convert_to_date(item[\'trade_date\'])\n\t\t\t\t\t\ttry:',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'trade_date\',))\n\t\t\t\t\tfor item in data:\n\t\t\t\t\t\ttry:'),

    # 8. _sync_etf_share (trade_date)
    ('3454_etf_share',
     '\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'trade_date\'): item[\'trade_date\'] = _convert_to_date(item[\'trade_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'trade_date\',))\n\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\ttry:'),

    # 9. _sync_forecast (ann_date, end_date)
    ('3529_forecast',
     '\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'))\n\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\ttry:'),

    # 10. _sync_express (ann_date, end_date)
    ('3601_express',
     '\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'))\n\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\ttry:'),

    # 11. _sync_dividend (ann_date)
    ('3672_dividend',
     '\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\',))\n\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\ttry:'),

    # 12. _sync_financial_indicator (ann_date, end_date, known_cols)
    ('3750_fina_indicator',
     '\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'), known_cols=known_cols)\n\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\ttry:'),

    # 13. _sync_audit_opinion (ann_date, end_date, known_cols)
    ('3833_audit_opinion',
     '\t\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'), known_cols=known_cols)\n\t\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\t\ttry:'),

    # 14. _sync_business_income (end_date, known_cols)
    ('3914_business_income',
     '\t\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'end_date\',), known_cols=known_cols)\n\t\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\t\ttry:'),
]

applied = 0
for name, old, new in fixes:
    if old in content:
        content = content.replace(old, new)
        applied += 1
        print(f'OK  {name}')
    else:
        print(f'NO  {name}')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

# Verify syntax
try:
    ast.parse(content)
    print(f'\nApplied {applied}/{len(fixes)}. Syntax OK.')
    remaining = len(re.findall(r'_clean_nan_values\(item\)', content))
    preprocess_refs = len(re.findall(r'_preprocess_records', content))
    print(f'_clean_nan_values(item) remaining: {remaining}')
    print(f'_preprocess_records refs: {preprocess_refs}')
except SyntaxError as e:
    print(f'\nApplied {applied}. SYNTAX ERROR line {e.lineno}')
    lines = content.split('\n')
    for i in range(max(0,e.lineno-3), min(len(lines),e.lineno+2)):
        print(f'  {i+1}: {repr(lines[i][:120])}')
