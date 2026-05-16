import dayjs from "dayjs";

export function formatDate(date: string | Date, format = "YYYY-MM-DD"): string {
  return dayjs(date).format(format);
}

export function formatDateTime(
  date: string | Date,
  format = "YYYY-MM-DD HH:mm:ss",
): string {
  return dayjs(date).format(format);
}

export function addDays(date: string | Date, days: number): Date {
  return dayjs(date).add(days, "day").toDate();
}

export function getTradeDates(
  startDate: string | Date,
  endDate: string | Date,
): string[] {
  const dates: string[] = [];
  let current = dayjs(startDate);
  const end = dayjs(endDate);

  while (current.isBefore(end) || current.isSame(end)) {
    if (current.day() !== 0 && current.day() !== 6) {
      dates.push(current.format("YYYY-MM-DD"));
    }
    current = current.add(1, "day");
  }

  return dates;
}
