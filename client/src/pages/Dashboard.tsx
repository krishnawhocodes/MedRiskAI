import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

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
  Upload,
  History as HistoryIcon,
  Eye,
  Loader2,
  TrendingUp,
  FileText,
  ShieldAlert,
} from "lucide-react";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

import { useAuth } from "./AuthContext";
import { db, appId } from "./firebase";
import {
  collection,
  query,
  onSnapshot,
  orderBy,
  limit,
  Timestamp,
} from "firebase/firestore";

/** -----------------------------
 * Types (loose + safe)
 * ----------------------------- */
type RiskLevel = "Low" | "Moderate" | "High" | string;

interface FirestoreReportDoc {
  id: string;
  fileName?: string;
  uploadedAt?: Timestamp;

  overallRisk?: RiskLevel;
  primaryCondition?: string;
  issuesFound?: number;
  markersChecked?: number;

  extractionMethod?: string;
  pagesProcessed?: number | null;

  analysisData?: any; // FULL analysis result from backend
}

function formatDate(ts?: Timestamp) {
  if (!ts) return "N/A";
  return ts.toDate().toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function riskVariant(risk?: string) {
  switch ((risk || "").toLowerCase()) {
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

function safeScore(report?: FirestoreReportDoc): number {
  const s = report?.analysisData?.prediction?.overall?.score;
  if (typeof s === "number" && !Number.isNaN(s))
    return Math.max(0, Math.min(100, s));

  const r = String(report?.overallRisk || "").toLowerCase();
  if (r === "high") return 85;
  if (r === "moderate") return 55;
  if (r === "low") return 25;
  return 0;
}

function scoreToProgress(score?: number) {
  if (typeof score !== "number" || Number.isNaN(score)) return 0;
  return Math.max(0, Math.min(100, score));
}

function getTopConditions(
  report?: FirestoreReportDoc,
): { key: string; score: number; level: string }[] {
  const a = report?.analysisData;

  // backend final payload may already include topConditions
  if (Array.isArray(a?.topConditions) && a.topConditions.length > 0) {
    return a.topConditions.slice(0, 4).map((x: any) => ({
      key: String(x.key || "Unknown"),
      score: typeof x.score === "number" ? x.score : 0,
      level: String(x.level || "Low"),
    }));
  }

  // otherwise compute from prediction.riskScores
  const riskScores = a?.prediction?.riskScores || {};
  const rows = Object.entries(riskScores).map(([k, v]: any) => ({
    key: String(k),
    score: typeof v?.score === "number" ? v.score : 0,
    level: String(v?.level || "Low"),
  }));

  rows.sort((x, y) => (y.score ?? 0) - (x.score ?? 0));
  return rows.slice(0, 4);
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, userId } = useAuth();

  const userName = user?.displayName || "User";

  const [reports, setReports] = useState<FirestoreReportDoc[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!userId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    const reportsCollectionPath = `artifacts/${appId}/users/${userId}/reports`;

    const q = query(
      collection(db, reportsCollectionPath),
      orderBy("uploadedAt", "desc"),
      limit(8),
    );

    const unsub = onSnapshot(
      q,
      (snap) => {
        const arr: FirestoreReportDoc[] = [];
        snap.forEach((doc) => arr.push({ id: doc.id, ...(doc.data() as any) }));
        setReports(arr);
        setIsLoading(false);
      },
      (err) => {
        console.error("Dashboard fetch error:", err);
        setIsLoading(false);
      },
    );

    return () => unsub();
  }, [userId]);

  const latest = reports[0];

  const topConditions = useMemo(() => getTopConditions(latest), [latest]);

  const riskTrend = useMemo(() => {
    // Reverse = older -> newer for chart
    const chronological = [...reports].reverse();

    return chronological.map((r, idx) => ({
      name: `R${idx + 1}`,
      date: formatDate(r.uploadedAt),
      score: Math.round(safeScore(r)),
    }));
  }, [reports]);

  const latestScore = useMemo(() => safeScore(latest), [latest]);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1">
        {/* HERO */}
        <section className="relative bg-gradient-to-br from-primary/5 via-background to-success/5 overflow-hidden">
          <div className="container mx-auto px-4 py-14 lg:py-20">
            <div className="grid lg:grid-cols-2 gap-10 items-center">
              <div className="space-y-6">
                <h1 className="text-4xl lg:text-5xl font-bold text-foreground leading-tight">
                  Welcome back, <span className="text-primary">{userName}</span>
                  !
                </h1>

                <p className="text-xl text-muted-foreground">
                  Upload your blood report and get AI-powered risk insights in
                  minutes.
                </p>

                <div className="flex flex-wrap gap-3">
                  <Button size="lg" onClick={() => navigate("/upload")}>
                    <Upload className="mr-2 h-5 w-5" />
                    Upload New Report
                  </Button>

                  <Button
                    size="lg"
                    variant="outline"
                    onClick={() => navigate("/history")}
                  >
                    <HistoryIcon className="mr-2 h-5 w-5" />
                    View History
                  </Button>
                </div>

                <p className="text-xs text-muted-foreground">
                  Tip: Scanned PDFs are supported — OCR runs automatically ✅
                </p>
              </div>

              <div className="hidden lg:block">
                <div className="rounded-xl border bg-card shadow-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <ShieldAlert className="h-6 w-6 text-primary" />
                    <div>
                      <p className="font-semibold text-foreground">
                        Quick Summary
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Your latest risk snapshot
                      </p>
                    </div>
                  </div>

                  {isLoading ? (
                    <div className="flex items-center justify-center py-10">
                      <Loader2 className="h-7 w-7 animate-spin text-primary" />
                    </div>
                  ) : !latest ? (
                    <div className="text-sm text-muted-foreground py-6">
                      No reports found. Upload your first report to see insights
                      here.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs text-muted-foreground">
                            Overall Risk
                          </p>
                          <p className="text-2xl font-bold text-foreground">
                            {latest.overallRisk || "Unknown"}
                          </p>
                        </div>
                        <Badge
                          variant={
                            riskVariant(String(latest.overallRisk || "")) as any
                          }
                        >
                          {(latest.overallRisk || "Unknown") + " Risk"}
                        </Badge>
                      </div>

                      <div>
                        <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                          <span>Overall Score</span>
                          <span className="font-medium text-foreground">
                            {Math.round(latestScore)}/100
                          </span>
                        </div>
                        <Progress value={scoreToProgress(latestScore)} />
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-lg border p-3">
                          <p className="text-xs text-muted-foreground">
                            Issues Found
                          </p>
                          <p className="text-lg font-semibold text-foreground">
                            {latest.issuesFound ??
                              latest.analysisData?.issuesFound ??
                              0}
                          </p>
                        </div>
                        <div className="rounded-lg border p-3">
                          <p className="text-xs text-muted-foreground">
                            Markers Checked
                          </p>
                          <p className="text-lg font-semibold text-foreground">
                            {latest.markersChecked ??
                              latest.analysisData?.markersChecked ??
                              0}
                          </p>
                        </div>
                      </div>

                      <Button
                        className="w-full"
                        onClick={() =>
                          navigate("/results", {
                            state: { reportData: latest.analysisData },
                          })
                        }
                      >
                        <Eye className="mr-2 h-4 w-4" />
                        View Full Report
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* MAIN INSIGHTS */}
        <section className="py-12">
          <div className="container mx-auto px-4">
            <div className="grid lg:grid-cols-3 gap-6">
              {/* Latest Report Card */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Latest Report Insights</CardTitle>
                  <CardDescription>
                    {isLoading
                      ? "Loading latest report..."
                      : latest
                        ? `Analyzed on ${formatDate(latest.uploadedAt)}`
                        : "Upload your first report to start tracking trends."}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  {isLoading ? (
                    <div className="flex items-center justify-center py-10">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    </div>
                  ) : !latest ? (
                    <div className="text-center text-muted-foreground py-8">
                      <FileText className="h-12 w-12 mx-auto mb-3" />
                      <p className="mb-4">No reports yet.</p>
                      <Button onClick={() => navigate("/upload")}>
                        Upload Report
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm text-muted-foreground">
                            Overall Risk
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge
                              variant={
                                riskVariant(
                                  String(latest.overallRisk || ""),
                                ) as any
                              }
                              className="text-sm"
                            >
                              {String(latest.overallRisk || "Unknown")}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                              {latest.primaryCondition ||
                                latest.analysisData?.primaryCondition ||
                                latest.analysisData?.prediction?.overall
                                  ?.primaryCondition ||
                                "General Health"}
                            </span>
                          </div>
                        </div>

                        <div className="min-w-[220px]">
                          <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                            <span>Overall Score</span>
                            <span className="font-medium text-foreground">
                              {Math.round(latestScore)}/100
                            </span>
                          </div>
                          <Progress value={scoreToProgress(latestScore)} />
                        </div>
                      </div>

                      <Separator />

                      {/* Top Conditions */}
                      <div>
                        <p className="font-semibold text-foreground mb-3">
                          Top Risk Signals
                        </p>

                        {topConditions.length === 0 ? (
                          <p className="text-sm text-muted-foreground">
                            No risk score breakdown found for this report.
                          </p>
                        ) : (
                          <div className="grid md:grid-cols-2 gap-3">
                            {topConditions.slice(0, 4).map((c) => (
                              <div
                                key={c.key}
                                className="rounded-lg border p-3 flex items-start justify-between gap-3"
                              >
                                <div className="min-w-0">
                                  <p className="text-sm text-muted-foreground">
                                    Condition
                                  </p>
                                  <p className="font-semibold truncate">
                                    {String(c.key).replace(" Risk", "")}
                                  </p>
                                  <p className="text-xs text-muted-foreground mt-1">
                                    Score: {Math.round(c.score)}/100
                                  </p>
                                </div>
                                <Badge variant={riskVariant(c.level) as any}>
                                  {c.level}
                                </Badge>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <Separator />

                      {/* Extraction info */}
                      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-2">
                          <TrendingUp className="h-4 w-4 text-primary" />
                          Extraction:{" "}
                          <span className="text-foreground font-medium">
                            {latest.extractionMethod ||
                              latest.analysisData?.extraction?.method ||
                              "digital"}
                          </span>
                        </span>

                        <span>
                          Pages:{" "}
                          <span className="text-foreground font-medium">
                            {latest.pagesProcessed ??
                              latest.analysisData?.extraction?.pages ??
                              "—"}
                          </span>
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-3">
                        <Button
                          onClick={() =>
                            navigate("/results", {
                              state: { reportData: latest.analysisData },
                            })
                          }
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          View Full Analysis
                        </Button>

                        <Button
                          variant="outline"
                          onClick={() => navigate("/history")}
                        >
                          <HistoryIcon className="mr-2 h-4 w-4" />
                          View All Reports
                        </Button>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Trend Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Risk Trend</CardTitle>
                  <CardDescription>
                    Recent overall score trend (last {reports.length} reports)
                  </CardDescription>
                </CardHeader>

                <CardContent className="h-[280px]">
                  {reports.length < 2 ? (
                    <div className="text-sm text-muted-foreground">
                      Upload at least 2 reports to see a trend chart.
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={riskTrend}
                        margin={{ left: 8, right: 8 }}
                      >
                        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                        <Tooltip
                          formatter={(value: any) => [`${value}/100`, "Score"]}
                          labelFormatter={(label) => `Report ${label}`}
                        />
                        <Line
                          type="monotone"
                          dataKey="score"
                          stroke="hsl(var(--primary))"
                          strokeWidth={3}
                          dot={{ r: 3 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Recent Reports List */}
            {!isLoading && reports.length > 0 && (
              <Card className="mt-8">
                <CardHeader>
                  <CardTitle>Recent Reports</CardTitle>
                  <CardDescription>
                    Quick access to your latest uploaded reports
                  </CardDescription>
                </CardHeader>

                <CardContent className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left border-b border-border">
                        <th className="py-2 pr-3">Date</th>
                        <th className="py-2 pr-3">File</th>
                        <th className="py-2 pr-3">Risk</th>
                        <th className="py-2 pr-3">Score</th>
                        <th className="py-2 pr-3">Extraction</th>
                        <th className="py-2 pr-3">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reports.slice(0, 6).map((r) => {
                        const sc = safeScore(r);
                        const method =
                          r.extractionMethod ||
                          r.analysisData?.extraction?.method ||
                          "digital";
                        return (
                          <tr key={r.id} className="border-b border-border/40">
                            <td className="py-2 pr-3 text-muted-foreground">
                              {formatDate(r.uploadedAt)}
                            </td>
                            <td className="py-2 pr-3 font-medium">
                              {r.fileName || "Report Analysis"}
                            </td>
                            <td className="py-2 pr-3">
                              <Badge
                                variant={
                                  riskVariant(
                                    String(r.overallRisk || ""),
                                  ) as any
                                }
                              >
                                {String(r.overallRisk || "Unknown")}
                              </Badge>
                            </td>
                            <td className="py-2 pr-3 text-muted-foreground">
                              {Math.round(sc)}/100
                            </td>
                            <td className="py-2 pr-3 text-muted-foreground">
                              {String(method).toUpperCase()}
                            </td>
                            <td className="py-2 pr-3">
                              <Button
                                size="sm"
                                onClick={() =>
                                  navigate("/results", {
                                    state: { reportData: r.analysisData },
                                  })
                                }
                              >
                                <Eye className="mr-2 h-4 w-4" />
                                View
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            )}
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
