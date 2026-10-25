// Static 12-month projection used only as the landing-page hero visual: a baseline plus two options for
// a $1,100 purchase against the demo persona's floor. Built from a fixed table; never shown as advice.
import type { ProjectionResult } from "../types";
import { BASELINE_KEY, type ChartSeries } from "../components/ProjectionChart";

export const LANDING_FLOOR_CENTS = 20000;

const MONTHS = ["2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04", "2027-05", "2027-06", "2027-07", "2027-08", "2027-09", "2027-10"];

// End-of-month balances in dollars.
const BASELINE = [1268, 1410, 420, 590, 760, 930, 1100, 1270, 1440, 1610, 1780, 1950];
const FINANCED = [1171, 1216, 129, 202, 275, 348, 421, 494, 567, 640, 713, 786];
const CASH = [168, 310, -680, -510, -340, -170, 0, 170, 340, 510, 680, 850];

function build(optionId: string | null, dollars: number[]): ProjectionResult {
  const series = MONTHS.map((month, i) => {
    const end = dollars[i] * 100;
    return { month, end_balance_cents: end, min_balance_cents: end, min_balance_date: `${month}-28`, inflow_cents: 170000, outflow_cents: 0 };
  });
  let minIdx = 0;
  series.forEach((p, i) => {
    if (p.end_balance_cents < series[minIdx].end_balance_cents) minIdx = i;
  });
  return {
    option_id: optionId,
    series,
    min_balance_cents: series[minIdx].end_balance_cents,
    min_balance_date: series[minIdx].min_balance_date,
    monthly_slack_cents: 0,
    months_below_floor: series.filter((p) => p.end_balance_cents < LANDING_FLOOR_CENTS).map((p) => p.month),
    months_negative: series.filter((p) => p.end_balance_cents < 0).map((p) => p.month),
    flags: [],
    band: null,
  };
}

export const LANDING_SELECTED = "financed_12";

export const LANDING_SERIES: ChartSeries[] = [
  { id: BASELINE_KEY, label: "Don't buy", result: build(null, BASELINE) },
  { id: LANDING_SELECTED, label: "Finance over 12 months", result: build(LANDING_SELECTED, FINANCED) },
  { id: "cash_now", label: "Pay in cash", result: build("cash_now", CASH) },
];
