import re
path = 'quant_server/modules/data/services/sync_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

fixes = [
    # _sync_financial_indicator
    ('\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\ttry:',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'), known_cols=known_cols)\n\t\t\t\t\ttry:'),

    # _sync_audit_opinion
    ('\t\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'), known_cols=known_cols)\n\t\t\t\t\t\t\ttry:'),

    # _sync_business_income
    ('\t\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\t\titem = {k: v for k, v in item.items() if k in known_cols}\n\t\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'end_date\',), known_cols=known_cols)\n\t\t\t\t\t\t\ttry:'),

    # _sync_forecast
    ('\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\', \'end_date\'))\n\t\t\t\t\t\ttry:'),

    # _sync_express (same pattern)
    ('\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\tif item.get(\'end_date\'): item[\'end_date\'] = _convert_to_date(item[\'end_date\'])\n\t\t\t\t\t\t\ttry:',
     None),  # handled by forecast pattern above, skip

    # _sync_dividend
    ('\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'ann_date\'): item[\'ann_date\'] = _convert_to_date(item[\'ann_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'ann_date\',))\n\t\t\t\t\t\ttry:'),

    # _sync_suspend_info
    ('\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\tif item.get(\'trade_date\'): item[\'trade_date\'] = _convert_to_date(item[\'trade_date\'])\n\t\t\t\t\t\ttry:',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'trade_date\',))\n\t\t\t\t\ttry:'),

    # _sync_etf_share
    ('\t\t\t\t\t\tfor item in data:\n\t\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t\tif item.get(\'trade_date\'): item[\'trade_date\'] = _convert_to_date(item[\'trade_date\'])\n\t\t\t\t\t\t\ttry:',
     '\t\t\t\t\t\t_preprocess_records(data, date_fields=(\'trade_date\',))\n\t\t\t\t\t\ttry:'),

    # _sync_index_basic
    ('\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\t# 转换所有日期字段（Tushare 返回 \"19901219\" 格式字符串）\n\t\t\t\t\t\tfor date_field in (\'list_date\', \'base_date\', \'exp_date\'):\n\t\t\t\t\t\t\tif item.get(date_field):\n\t\t\t\t\t\t\t\titem[date_field] = _convert_to_date(item[date_field])\n\t\t\t\t\t\texisting = await self.index_basic_repo.get_by(ts_code=item[\"ts_code\"])',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'list_date\', \'base_date\', \'exp_date\'))\n\t\t\t\t\texisting = await self.index_basic_repo.get_by(ts_code=item[\"ts_code\"])'),

    # _sync_etf_index
    ('\t\t\t\t\tfor item in data:\n\t\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\t\tif item.get(\'pub_date\'):\n\t\t\t\t\t\t\titem[\'pub_date\'] = _convert_to_date(item[\'pub_date\'])\n\t\t\t\t\t\ttry:',
     '\t\t\t\t\t_preprocess_records(data, date_fields=(\'pub_date\',))\n\t\t\t\t\t\ttry:'),

    # _sync_stock_company
    ('\t\t\t\tfor item in data:\n\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\tif \'setup_date\' in item and item[\'setup_date\']:\n\t\t\t\t\t\titem[\'setup_date\'] = _convert_to_date(item[\'setup_date\'])\n\t\t\t\t\texisting = await self.company_repo.get_by(ts_code=item[\"ts_code\"])',
     '\t\t\t\t_preprocess_records(data, date_fields=(\'setup_date\',))\n\t\t\t\t\texisting = await self.company_repo.get_by(ts_code=item[\"ts_code\"])'),

    # _sync_st_list
    ('\t\t\t\tfor item in data:\n\t\t\t\t\titem = _clean_nan_values(item)\n\t\t\t\t\tif \'start_date\' in item and item[\'start_date\']:\n\t\t\t\t\t\titem[\'trade_date\'] = _convert_to_date(item[\'start_date\'])\n\t\t\t\t\tname = item.get(\'name\',\'\')',
     '\t\t\t\t_preprocess_records(data, date_fields=(\'start_date\',))\n\t\t\t\t\tfor item in data:\n\t\t\t\t\t\tif item.get(\'start_date\'): item[\'trade_date\'] = item[\'start_date\']\n\t\t\t\t\tname = item.get(\'name\',\'\')'),
]

count = 0
for old, new in fixes:
    if new is None:
        continue
    if old in content:
        content = content.replace(old, new)
        count += 1
    else:
        idx = content.find(old[:40])
        if idx > 0:
            print(f'PARTIAL match for: {old[:40]}...')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Applied {count}/{len([f for f in fixes if f[1] is not None])} fixes')
