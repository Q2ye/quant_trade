// 日期处理
import dayjs from 'dayjs';
export function formatDate(date, format = 'YYYY-MM-DD') {
  return dayjs(date).format(format);
}
export function formatDateTime(date, format = 'YYYY-MM-DD HH:mm:ss') {
  return dayjs(date).format(format);
}
export function addDays(date, days) {
  return dayjs(date).add(days, 'day').toDate();
}
export function getTradeDates(startDate, endDate) {
  // 实际项目中应调用API获取交易日历
  const dates = [];
  let current = dayjs(startDate);
  const end = dayjs(endDate);

  while (current.isBefore(end) || current.isSame(end)) {
    // 跳过周末（实际应使用交易日历）
    if (current.day() !== 0 && current.day() !== 6) {
      dates.push(current.format('YYYY-MM-DD'));
    }
    current = current.add(1, 'day');
  }

  return dates;
}