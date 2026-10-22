import { todayISO } from './dates.mjs';

export function telemetry(facts, now = new Date()) {
  const day = todayISO(now), [year, month, date] = day.split('-').map(Number);
  const instant = Date.UTC(year, month - 1, date, 12);
  const dayNumber = Math.floor((Date.UTC(year, month - 1, date) - Date.UTC(year, 0, 1)) / 86400000) + 1;
  const daysInYear = (Date.UTC(year + 1, 0, 1) - Date.UTC(year, 0, 1)) / 86400000;
  // Approximate lunar phase from a known new moon and the mean synodic month.
  const period = 29.530588853;
  const elapsed = (instant - Date.UTC(2000, 0, 6, 18, 14)) / 86400000;
  const cycle = ((elapsed % period) + period) % period / period;
  const phases = ['new moon', 'waxing crescent', 'first quarter', 'waxing gibbous', 'full moon', 'waning gibbous', 'last quarter', 'waning crescent'];
  const dayIndex = Math.floor(instant / 86400000);
  return { year, dayNumber, daysInYear, moon: phases[Math.round(cycle * 8) % 8], fact: facts[((dayIndex % facts.length) + facts.length) % facts.length] };
}
