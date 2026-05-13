import type { TourStepDef } from "../../../components/tour/Tour";

// Trial value type matching backend TrialValueResponse
export interface TrialValue {
  total_opportunities: number;
  total_value: number;
  searches_executed: number;
  avg_opportunity_value: number;
  top_opportunity: { title: string; value: number } | null;
}
