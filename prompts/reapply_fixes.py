import re

path = 'quant_server/modules/data/services/sync_service.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

applied = 0

# === 1. Add INDEX_BASIC/INDEX_DAILY/MANAGERS/REWARDS to _sync_method_map ===
old = 'DataType.CALENDAR: self._sync_trade_calendar,\n\t\t}'
new = ('DataType.INDEX_BASIC: self._sync_index_basic,\n\t\t'
       'DataType.INDEX_DAILY: self._sync_index_daily,\n\t\t'
       'DataType.MANAGERS: self._sync_stk_managers,\n\t\t'
       'DataType.REWARDS: self._sync_stk_rewards,\n\t\t'
       'DataType.CALENDAR: self._sync_trade_calendar,\n\t\t}')
if old in content:
    content = content.replace(old, new)
    applied += 1
    print('1. _sync_method_map: added 4 missing entries')
else:
    print('1. FAILED: _sync_method_map')

# === 2. _process_trade_date_data → use bulk_upsert ===
old = '\tasync def _process_trade_date_data(\n\t\t\trepo,\n\t\t\tdata: List[Dict],\n\t\t\tts_code: str\n\t) -> Tuple[int, int]:\n\t\t"""处理带有trade_date的数据"""\n\t\trecords_added = 0\n\t\trecords_updated = 0\n\t\tfor item in data:\n\t\t\t# 转换trade_date为date对象\n\t\t\ttrade_date = _convert_to_date(item.get(\'trade_date\'))\n\t\t\titem[\'trade_date\'] = trade_date\n\n\t\t\texisting_list = await repo.get_by_trade_date(\n\t\t\t\tts_code=ts_code,\n\t\t\t\ttrade_date=trade_date\n\t\t\t)\n\t\t\texisting = existing_list[0] if existing_list else None\n\t\t\tif existing:\n\t\t\t\t# 尝试使用update_by方法（ETF），如果失败则使用update方法（股票）\n\t\t\t\ttry:\n\t\t\t\t\tawait repo.update_by(\n\t\t\t\t\t\t{"ts_code": existing.ts_code, "trade_date": existing.trade_date},\n\t\t\t\t\t\titem\n\t\t\t\t\t)\n\t\t\t\texcept AttributeError:\n\t\t\t\t\tawait repo.update(existing.id, item)\n\t\t\t\trecords_updated += 1\n\t\t\telse:\n\t\t\t\tawait repo.create(item)\n\t\t\t\trecords_added += 1\n\t\treturn records_added, records_updated'

# Check if old exists
if old in content:
    new_method = ('\tasync def _process_trade_date_data(\n\t\t\tself,\n\t\t\trepo,\n\t\t\tdata: List[Dict],\n\t\t\tts_code: str,\n\t) -> Tuple[int, int]:\n\t\t"""处理 trade_date 数据，repo 有 bulk_upsert 时走批量。"""\n\t\tfor item in data:\n\t\t\titem[\'trade_date\'] = _convert_to_date(item.get(\'trade_date\'))\n\t\tif hasattr(repo, \'bulk_upsert\'):\n\t\t\treturn await repo.bulk_upsert(data), 0\n\t\treturn await self._process_trade_date_data_fallback(repo, data, ts_code)')
    content = content.replace(old, new_method)
    applied += 1
    print('2. _process_trade_date_data: simplified to Facade')
else:
    # Try finding the original signature
    idx = content.find('async def _process_trade_date_data(')
    if idx > 0:
        print(f'2. Found at offset {idx}, checking content...')
        snippet = content[idx:idx+50]
        print(f'   {repr(snippet)}')

# === 3. Add _is_cancelled with DB check ===
# Find the method before _resolve_sync_date_range
old_is_cancel = 'async def _resolve_sync_date_range ('
# Add _is_cancelled before it
new_is_cancel = (
    '\t# ==================== 取消检查 ====================\n\n'
    '\tasync def _is_cancelled(self) -> bool:\n'
    '\t\t"""双重取消检查：token（O(1)）→ DB（首次缓存后 O(1)）。"""\n'
    '\t\tif self.cancel_token and self.cancel_token.is_set():\n\t\t\treturn True\n'
    '\t\tif self._task_id and not getattr(self, \'_db_cancel_checked\', False):\n'
    '\t\t\tself._db_cancel_checked = True\n'
    '\t\t\ttry:\n'
    '\t\t\t\ttask = await self.sync_task_repo.get_by_task_id(self._task_id)\n'
    '\t\t\t\tif task and task.data and getattr(task.data, \'status\', None) == \'cancelled\':\n'
    '\t\t\t\t\tif self.cancel_token:\n\t\t\t\t\t\tself.cancel_token.set()\n\t\t\t\t\treturn True\n'
    '\t\t\texcept Exception:\n\t\t\t\tpass\n'
    '\t\treturn False\n\n'
    '\tasync def _resolve_sync_date_range ('
)
if old_is_cancel in content:
    content = content.replace(old_is_cancel, new_is_cancel)
    applied += 1
    print('3. _is_cancelled: added with DB check')
else:
    print('3. FAILED: _resolve_sync_date_range not found')

# === 4. Add _task_id to __init__ ===
old_init = 'self.cancel_token = cancel_token  # asyncio.Event or None\n\n\t\t# ========== 初始化Repository'
new_init = 'self.cancel_token = cancel_token  # asyncio.Event or None\n\t\tself._task_id = None  # 由调用方注入，用于 _is_cancelled DB 回退\n\n\t\t# ========== 初始化Repository'
if old_init in content:
    content = content.replace(old_init, new_init)
    applied += 1
    print('4. __init__: added _task_id')
else:
    print('4. FAILED: cancel_token init not found')

# === 5. Fix get_moneyflow param ===
old_money = 'source.get_moneyflow, ts_code=ts_code,'
new_money = 'source.get_moneyflow, symbol=ts_code,'
if old_money in content:
    content = content.replace(old_money, new_money)
    applied += 1
    print('5. get_moneyflow: ts_code= → symbol=')
else:
    print('5. get_moneyflow: already fixed or not found')

# === 6. Full mode date passing for _sync_index_daily ===
# Add start_date default and full mode check
old_idx_loop = '\t\tfor idx, index_code in enumerate(ts_codes):\n\t\t\tif self.cancel_token and self.cancel_token.is_set(): break\n\t\t\ts_date, e_date, mode = await self._resolve_sync_date_range(index_code, start_date, end_date, self.index_daily_repo)'
new_idx_loop = ('\t\tif not start_date:\n\t\t\tstart_date = datetime.now().date() - timedelta(days=365)\n'
                '\t\tfor idx, index_code in enumerate(ts_codes):\n'
                '\t\t\tif await self._is_cancelled(): break\n'
                '\t\t\ts_date, e_date, mode = await self._resolve_sync_date_range(index_code, start_date, end_date, self.index_daily_repo)')
if old_idx_loop in content:
    content = content.replace(old_idx_loop, new_idx_loop)
    applied += 1
    print('6. _sync_index_daily: start_date default + _is_cancelled')
else:
    print('6. _sync_index_daily: pattern not found, searching...')
    idx = content.find('_sync_index_daily')
    if idx > 0:
        print(f'   Found at {idx}: {repr(content[idx:idx+80])}')

# === 7. Full mode date fix for index_daily ===
old_full = ("s_str = s_date.strftime('%Y%m%d') if s_date else ''\n\t\t\te_str = e_date.strftime('%Y%m%d') if e_date else ''\n\t\t\ttry:\n\t\t\t\tdf = await self._run_in_executor(source.get_index_daily, ts_code=index_code, start_date=start_date_str, end_date=end_date_str)")
if old_full in content:
    new_full = ("if mode == 'full':\n\t\t\t\tdf = await self._run_in_executor(source.get_index_daily, ts_code=index_code)\n\t\t\telse:\n\t\t\t\tstart_date_str = s_date.strftime('%Y%m%d') if s_date else ''\n\t\t\t\tend_date_str = e_date.strftime('%Y%m%d') if e_date else ''\n\t\t\t\tdf = await self._run_in_executor(source.get_index_daily, ts_code=index_code, start_date=start_date_str, end_date=end_date_str)")
    content = content.replace(old_full, new_full)
    applied += 1
    print('7. _sync_index_daily: full mode without dates')
else:
    print('7. _sync_index_daily full mode: pattern not found')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nTotal applied: {applied}/7 fixes')
