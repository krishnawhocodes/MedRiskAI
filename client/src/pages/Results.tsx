import { useEffect, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import Navbar from "../components/Navbar";
import Footer from "../components/Footer";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import {
  AlertCircle,
  CheckCircle2,
  Download,
  MapPin,
  TrendingUp,
  Activity,
} from "lucide-react";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";

/** --------------------------------
 * Types
 * -------------------------------- */
interface Finding {
  biomarker: string;
  value: string;
  normalRange: string;
  status: string;
  risk: "Low" | "Moderate" | "High" | string;
  interpretation: string;
  recommendation: string;
  specialties: string[];
}

type BiomarkerStatus = "normal" | "high" | "low" | "unknown";

interface BiomarkerRow {
  key: string;
  value: number | null;
  unit?: string | null;
  low?: number | null;
  high?: number | null;
  status: BiomarkerStatus;
  source?: string;
}

interface PredictionCondition {
  key: string;
  score: number;
  level: "Low" | "Moderate" | "High";
  reasons: string[];
  actions?: string[];
  markers?: Record<string, unknown>;
}

interface PredictionPayload {
  overall?: {
    score?: number;
    level?: "Low" | "Moderate" | "High";
    primaryCondition?: string;
  };
  riskScores?: Record<string, PredictionCondition>;
  flags?: Record<string, string>;
  engine?: Record<string, unknown>;
}

interface TopCondition {
  key: string;
  score: number;
  level: "Low" | "Moderate" | "High";
  reasons: string[];
}

type Urgency = "routine" | "soon" | "urgent" | string;

interface ProbableCondition {
  name: string;
  confidence: number; // 0..1
  severity: "Low" | "Moderate" | "High" | string;
  urgency: Urgency;
  why: string[];
  suggestedSpecialties: string[];
  nextSteps: string[];
  supportingMarkers?: Array<{
    key: string;
    value: number;
    unit?: string | null;
    low?: number | null;
    high?: number | null;
    status?: string;
    severity?: string;
    source?: string;
  }>;
  tags?: string[];
}

interface ClinicalInferencePayload {
  top?: ProbableCondition | null;
  conditions?: ProbableCondition[];
  notes?: string[];
}

interface ReportData {
  date: string;
  labName: string;
  overallRisk: "Low" | "Moderate" | "High" | string;
  primaryCondition?: string;
  issuesFound: number;
  markersChecked: number;
  findings: Finding[];

  prediction?: PredictionPayload;
  topConditions?: TopCondition[];
  biomarkerTable?: BiomarkerRow[];
  qualitative?: Record<string, { result?: string; titer?: string }>;

  // ✅ New fields (from backend finalize_report_payload)
  clinicalInference?: ClinicalInferencePayload;
  probableConditions?: ProbableCondition[];

  extraction?: {
    method?: string;
    pages?: number;
    warnings?: string[];
    used_llm?: boolean;
    [k: string]: any;
  };
}

/** --------------------------------
 * Helpers
 * -------------------------------- */
function toTitleCase(s: string) {
  return (s || "")
    .toLowerCase()
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function fmtNum(n: number | null | undefined, digits = 2) {
  if (typeof n !== "number" || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 100) return String(Math.round(n));
  return n.toFixed(digits);
}

function getRiskBadgeVariant(level: string) {
  switch ((level || "").toLowerCase()) {
    case "high":
      return "destructive";
    case "moderate":
      return "warning";
    case "low":
      return "success";
    default:
      return "secondary";
  }
}

function getStatusBadgeVariant(status: BiomarkerStatus) {
  if (status === "high") return "destructive";
  if (status === "low") return "warning";
  if (status === "normal") return "success";
  return "secondary";
}

function scoreToProgress(score?: number) {
  if (typeof score !== "number" || Number.isNaN(score)) return 0;
  return Math.max(0, Math.min(100, score));
}

function urgencyVariant(u: Urgency) {
  const x = String(u || "").toLowerCase();
  if (x === "urgent") return "destructive";
  if (x === "soon") return "warning";
  if (x === "routine") return "secondary";
  return "secondary";
}

function recommendedSpecialtyFromReport(reportData: ReportData): string {
  const inferredTop = reportData?.clinicalInference?.top;
  const inferred = inferredTop?.suggestedSpecialties?.[0];
  if (inferred) return inferred;

  const primary =
    reportData?.primaryCondition ||
    reportData?.prediction?.overall?.primaryCondition ||
    "";

  const topKey = reportData?.topConditions?.[0]?.key || "";
  const text = `${primary} ${topKey}`.toLowerCase();

  if (text.includes("cardio") || text.includes("heart")) return "Cardiologist";
  if (text.includes("diabetes") || text.includes("glucose"))
    return "Endocrinologist";
  if (text.includes("thyroid")) return "Endocrinologist";
  if (text.includes("kidney") || text.includes("renal")) return "Nephrologist";
  if (text.includes("liver") || text.includes("hepat"))
    return "Gastroenterologist";
  if (text.includes("anemia") || text.includes("blood")) return "Hematologist";

  return "General Physician";
}

const PIE_COLORS: Record<BiomarkerStatus, string> = {
  normal: "hsl(var(--success))",
  high: "hsl(var(--destructive))",
  low: "hsl(var(--warning))",
  unknown: "hsl(var(--muted-foreground))",
};

export default function Results() {
  const navigate = useNavigate();
  const loc = useLocation();

  const reportData = (loc.state as any)?.reportData as ReportData | undefined;

  useEffect(() => {
    if (!reportData) {
      navigate("/upload", { replace: true });
    }
  }, [reportData, navigate]);

  if (!reportData) return null;

  const prediction = reportData.prediction;
  const overallScore = prediction?.overall?.score;

  const riskScores = prediction?.riskScores ?? {};
  const biomarkerTable = reportData.biomarkerTable ?? [];
  const topConditions = reportData.topConditions ?? [];
  const probableConditions =
    reportData.probableConditions ??
    reportData.clinicalInference?.conditions ??
    [];

  const computedTopConditions = useMemo<TopCondition[]>(() => {
    if (topConditions.length > 0) return topConditions;

    const rows: TopCondition[] = Object.entries(riskScores)
      .map(([k, v]) => ({
        key: k,
        score: typeof v?.score === "number" ? v.score : 0,
        level: (v?.level as any) || "Low",
        reasons: Array.isArray(v?.reasons) ? v.reasons : [],
      }))
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, 4);

    return rows;
  }, [topConditions, riskScores]);

  const conditionChartData = useMemo(() => {
    return Object.entries(riskScores)
      .map(([k, v]) => ({
        name: k.replace(" Risk", ""),
        score: typeof v?.score === "number" ? Math.round(v.score) : 0,
        level: (v?.level as any) || "Low",
      }))
      .sort((a, b) => b.score - a.score);
  }, [riskScores]);

  const pieData = useMemo(() => {
    const counts = { normal: 0, high: 0, low: 0, unknown: 0 };

    for (const row of biomarkerTable) {
      const st = row?.status || "unknown";
      if (st === "high") counts.high += 1;
      else if (st === "low") counts.low += 1;
      else if (st === "normal") counts.normal += 1;
      else counts.unknown += 1;
    }

    return (Object.keys(counts) as BiomarkerStatus[])
      .map((k) => ({ name: toTitleCase(k), key: k, value: counts[k] }))
      .filter((d) => d.value > 0);
  }, [biomarkerTable]);

  const abnormalBiomarkers = useMemo(() => {
    return biomarkerTable
      .filter((r) => r.status === "high" || r.status === "low")
      .slice(0, 12);
  }, [biomarkerTable]);

  const recommendedSpecialty = recommendedSpecialtyFromReport(reportData);

  const alternateSpecialties = useMemo(() => {
    const set = new Set<string>();
    for (const c of probableConditions.slice(0, 3)) {
      for (const sp of c?.suggestedSpecialties || []) set.add(sp);
    }
    set.delete(recommendedSpecialty);
    return Array.from(set).slice(0, 3);
  }, [probableConditions, recommendedSpecialty]);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-12">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <h1 className="text-3xl font-bold text-foreground mb-2">
                  Report Analysis
                </h1>
                <p className="text-muted-foreground">
                  {reportData.labName ? `${reportData.labName} • ` : ""}
                  {reportData.date || "Date not found"}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <Button variant="outline" disabled>
                  <Download className="mr-2 h-4 w-4" />
                  Download PDF (Coming Soon)
                </Button>
              </div>
            </div>
          </div>

          {/* Summary (4 cards) */}
          <div className="grid md:grid-cols-4 gap-4 mb-8">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">
                      Overall Risk
                    </p>
                    <p className="text-2xl font-bold text-foreground">
                      {reportData.overallRisk}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {reportData.primaryCondition ||
                        prediction?.overall?.primaryCondition ||
                        "General Health"}
                    </p>
                  </div>
                  {String(reportData.overallRisk).toLowerCase() === "high" ? (
                    <AlertCircle className="h-8 w-8 text-destructive" />
                  ) : (
                    <CheckCircle2 className="h-8 w-8 text-success" />
                  )}
                </div>

                {typeof overallScore === "number" && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between text-sm text-muted-foreground mb-2">
                      <span>Risk Score</span>
                      <span className="font-medium text-foreground">
                        {Math.round(overallScore)}/100
                      </span>
                    </div>
                    <Progress value={scoreToProgress(overallScore)} />
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">
                      Issues Found
                    </p>
                    <p className="text-2xl font-bold text-foreground">
                      {reportData.issuesFound}
                    </p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-warning" />
                </div>
                <p className="text-xs text-muted-foreground mt-3">
                  Abnormal markers + reactive screenings
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">
                      Markers Checked
                    </p>
                    <p className="text-2xl font-bold text-foreground">
                      {reportData.markersChecked}
                    </p>
                  </div>
                  <CheckCircle2 className="h-8 w-8 text-success" />
                </div>
                <p className="text-xs text-muted-foreground mt-3">
                  Extracted from PDF + OCR fallback if needed
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground mb-1">
                  Extraction Method
                </p>
                <p className="text-2xl font-bold text-foreground">
                  {toTitleCase(
                    String(reportData.extraction?.method || "digital"),
                  )}
                </p>
                <p className="text-xs text-muted-foreground mt-3">
                  Pages processed:{" "}
                  <span className="text-foreground font-medium">
                    {reportData.extraction?.pages ?? "—"}
                  </span>
                </p>
                {Array.isArray(reportData.extraction?.warnings) &&
                  reportData.extraction!.warnings!.length > 0 && (
                    <p className="text-xs text-muted-foreground mt-2">
                      Warnings:{" "}
                      {reportData.extraction!.warnings!.slice(0, 2).join(" • ")}
                    </p>
                  )}
              </CardContent>
            </Card>
          </div>

          {/* Combination-based probable conditions */}
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-primary" />
                Probable Patterns (Combination-Based)
              </CardTitle>
              <CardDescription>
                Explainable screening patterns based on combinations of
                biomarkers (not a diagnosis).
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {probableConditions.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  No combination-based patterns were generated for this report.
                </div>
              ) : (
                <div className="grid md:grid-cols-2 gap-4">
                  {probableConditions.slice(0, 4).map((c, idx) => (
                    <Card
                      key={`${c.name}-${idx}`}
                      className="border border-border/60"
                    >
                      <CardContent className="pt-5 space-y-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-semibold">{c.name}</p>
                            <p className="text-xs text-muted-foreground">
                              Confidence:{" "}
                              <span className="text-foreground font-medium">
                                {Math.round((c.confidence || 0) * 100)}%
                              </span>
                            </p>
                          </div>
                          <div className="flex flex-col items-end gap-2">
                            <Badge variant={getRiskBadgeVariant(c.severity)}>
                              {c.severity}
                            </Badge>
                            <Badge variant={urgencyVariant(c.urgency)}>
                              {toTitleCase(String(c.urgency))}
                            </Badge>
                          </div>
                        </div>

                        {Array.isArray(c.why) && c.why[0] && (
                          <p className="text-xs text-muted-foreground">
                            {c.why[0]}
                          </p>
                        )}

                        {Array.isArray(c.suggestedSpecialties) &&
                          c.suggestedSpecialties.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {c.suggestedSpecialties.slice(0, 3).map((sp) => (
                                <Button
                                  key={sp}
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    navigate(
                                      `/find-doctor?specialty=${encodeURIComponent(sp)}`,
                                    )
                                  }
                                >
                                  <MapPin className="h-4 w-4 mr-1" />
                                  {sp}
                                </Button>
                              ))}
                            </div>
                          )}

                        {Array.isArray(c.nextSteps) && c.nextSteps[0] && (
                          <p className="text-xs text-muted-foreground">
                            Next: {c.nextSteps[0]}
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              {Array.isArray(reportData.clinicalInference?.notes) &&
                reportData.clinicalInference!.notes!.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    {reportData
                      .clinicalInference!.notes!.slice(0, 2)
                      .map((n, i) => (
                        <div key={i}>• {n}</div>
                      ))}
                  </div>
                )}
            </CardContent>
          </Card>

          {/* Doctor recommendation (Top CTA) */}
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Recommended Doctors Near You</CardTitle>
              <CardDescription>
                Based on your report, we’ll show nearby doctors on a map.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex items-center justify-between flex-wrap gap-3">
              <div className="text-sm text-muted-foreground">
                Suggested specialty:{" "}
                <span className="font-semibold text-foreground">
                  {recommendedSpecialty}
                </span>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  onClick={() =>
                    navigate(
                      `/find-doctor?specialty=${encodeURIComponent(recommendedSpecialty)}`,
                    )
                  }
                >
                  Find Doctors on Map
                </Button>

                {alternateSpecialties.map((sp) => (
                  <Button
                    key={sp}
                    variant="outline"
                    onClick={() =>
                      navigate(
                        `/find-doctor?specialty=${encodeURIComponent(sp)}`,
                      )
                    }
                  >
                    {sp}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Risk Overview */}
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Risk Overview</CardTitle>
              <CardDescription>
                Predicted risks based on extracted biomarkers.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-6">
              {computedTopConditions.length > 0 ? (
                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {computedTopConditions.map((c) => (
                    <Card key={c.key} className="border border-border/60">
                      <CardContent className="pt-5">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm text-muted-foreground">
                              Condition
                            </p>
                            <p className="font-semibold truncate">
                              {c.key.replace(" Risk", "")}
                            </p>
                          </div>
                          <Badge variant={getRiskBadgeVariant(c.level)}>
                            {c.level}
                          </Badge>
                        </div>

                        <div className="mt-4">
                          <div className="flex items-center justify-between text-sm text-muted-foreground mb-2">
                            <span>Score</span>
                            <span className="font-medium text-foreground">
                              {Math.round(c.score)}/100
                            </span>
                          </div>
                          <Progress value={scoreToProgress(c.score)} />
                        </div>

                        {c.reasons?.[0] && (
                          <p className="text-xs text-muted-foreground mt-3">
                            {c.reasons[0]}
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  Prediction data not available for this report.
                </div>
              )}

              <Separator />

              <div className="grid lg:grid-cols-2 gap-6">
                <Card className="border border-border/60">
                  <CardHeader>
                    <CardTitle className="text-base">
                      Condition Risk Scores
                    </CardTitle>
                    <CardDescription>
                      Higher score = higher clinical risk signal
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[280px]">
                    {conditionChartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={conditionChartData}
                          margin={{ left: 8, right: 8 }}
                        >
                          <XAxis
                            dataKey="name"
                            tick={{ fontSize: 12 }}
                            interval={0}
                            angle={-18}
                            height={55}
                          />
                          <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                          <Tooltip
                            formatter={(value: any) => [
                              `${value}/100`,
                              "Score",
                            ]}
                          />
                          <Bar
                            dataKey="score"
                            fill="hsl(var(--primary))"
                            radius={[6, 6, 0, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="text-sm text-muted-foreground">
                        No condition scores found.
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="border border-border/60">
                  <CardHeader>
                    <CardTitle className="text-base">
                      Biomarker Status Breakdown
                    </CardTitle>
                    <CardDescription>
                      Normal vs high/low values (based on reference ranges)
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[280px]">
                    {pieData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={pieData}
                            dataKey="value"
                            nameKey="name"
                            innerRadius={55}
                            outerRadius={90}
                            paddingAngle={2}
                          >
                            {pieData.map((entry) => (
                              <Cell
                                key={entry.key}
                                fill={PIE_COLORS[entry.key as BiomarkerStatus]}
                              />
                            ))}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="text-sm text-muted-foreground">
                        Biomarker table not available for this report.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>

          {/* Abnormal Biomarkers */}
          {abnormalBiomarkers.length > 0 && (
            <Card className="mb-8">
              <CardHeader>
                <CardTitle>Abnormal Biomarkers</CardTitle>
                <CardDescription>
                  Markers outside the reference range (Top{" "}
                  {abnormalBiomarkers.length})
                </CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left border-b border-border">
                      <th className="py-2 pr-3">Marker</th>
                      <th className="py-2 pr-3">Value</th>
                      <th className="py-2 pr-3">Reference</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 pr-3">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {abnormalBiomarkers.map((r) => (
                      <tr key={r.key} className="border-b border-border/40">
                        <td className="py-2 pr-3 font-medium">{r.key}</td>
                        <td className="py-2 pr-3">
                          {fmtNum(r.value)} {r.unit || ""}
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">
                          {fmtNum(r.low)} – {fmtNum(r.high)} {r.unit || ""}
                        </td>
                        <td className="py-2 pr-3">
                          <Badge variant={getStatusBadgeVariant(r.status)}>
                            {toTitleCase(r.status)}
                          </Badge>
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">
                          {r.source || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {/* Detailed Findings */}
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-foreground">
              Detailed Findings
            </h2>

            {reportData.findings?.length > 0 ? (
              reportData.findings.map((finding, index) => (
                <Card key={index} className="overflow-hidden">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="space-y-1">
                        <CardTitle className="text-xl">
                          {finding.biomarker}
                        </CardTitle>
                        <CardDescription className="text-base">
                          <span className="font-semibold">Your value: </span>
                          {finding.value}
                          <span className="ml-2 text-muted-foreground">
                            (Normal: {finding.normalRange})
                          </span>
                        </CardDescription>
                      </div>

                      <Badge
                        variant={getRiskBadgeVariant(finding.risk)}
                        className="flex items-center gap-1"
                      >
                        {finding.risk === "High" ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : finding.risk === "Moderate" ? (
                          <AlertCircle className="h-3 w-3" />
                        ) : (
                          <CheckCircle2 className="h-3 w-3" />
                        )}
                        {finding.risk} Risk
                      </Badge>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-4">
                    <div>
                      <h4 className="font-semibold mb-2">Interpretation</h4>
                      <p className="text-muted-foreground">
                        {finding.interpretation}
                      </p>
                    </div>

                    <div>
                      <h4 className="font-semibold mb-2">Recommendation</h4>
                      <p className="text-muted-foreground mb-3">
                        {finding.recommendation}
                      </p>

                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            navigate(
                              `/find-doctor?specialty=${encodeURIComponent(
                                finding.specialties?.[0] || "General Physician",
                              )}`,
                            )
                          }
                        >
                          <MapPin className="h-4 w-4 mr-1" />
                          Find {finding.specialties?.[0] || "Doctor"}
                        </Button>

                        {finding.specialties?.slice(1, 4)?.map((sp) => (
                          <Button
                            key={sp}
                            variant="secondary"
                            size="sm"
                            onClick={() =>
                              navigate(
                                `/find-doctor?specialty=${encodeURIComponent(sp)}`,
                              )
                            }
                          >
                            {sp}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <p className="text-muted-foreground">
                    No significant findings were detected from the extracted
                    biomarkers.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Footer actions */}
          <div className="mt-10 flex items-center justify-between gap-3 flex-wrap">
            <Button variant="outline" onClick={() => navigate("/upload")}>
              Upload Another Report
            </Button>
            <Button onClick={() => navigate("/")}>Back to Dashboard</Button>
          </div>

          <p className="text-xs text-muted-foreground mt-8">
            ⚠️ Disclaimer: This app provides automated screening-style insights
            based on extracted report values and is not a medical diagnosis.
            Always consult a qualified clinician for interpretation and next
            steps.
          </p>
        </div>
      </main>

      <Footer />
    </div>
  );
}
