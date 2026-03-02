import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  FileText,
  Eye,
  Download,
  Calendar,
  Loader2,
  Search,
  ArrowDownAZ,
  ArrowDownWideNarrow,
} from "lucide-react";

import { useAuth } from "./AuthContext";
import { db, appId } from "./firebase";

import {
  collection,
  query,
  onSnapshot,
  orderBy,
  Timestamp,
} from "firebase/firestore";

/** -----------------------------
 * Types
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

  analysisData?: any;
}

/** -----------------------------
 * Helpers
 * ----------------------------- */
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

function formatDate(ts?: Timestamp) {
  if (!ts) return "Unknown date";
  return ts.toDate().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
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

export default function History() {
  const navigate = useNavigate();
  const { userId } = useAuth();

  const [reports, setReports] = useState<FirestoreReportDoc[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // UI state
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState<
    "all" | "low" | "moderate" | "high"
  >("all");
  const [sortMode, setSortMode] = useState<"newest" | "oldest" | "highestRisk">(
    "newest",
  );

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
        console.error("History fetch error:", err);
        setIsLoading(false);
      },
    );

    return () => unsub();
  }, [userId]);

  const filtered = useMemo(() => {
    let arr = [...reports];

    // Search
    const q = search.trim().toLowerCase();
    if (q) {
      arr = arr.filter((r) => {
        const file = String(r.fileName || "").toLowerCase();
        const lab = String(r.analysisData?.labName || "").toLowerCase();
        const pc = String(
          r.primaryCondition || r.analysisData?.primaryCondition || "",
        ).toLowerCase();
        return file.includes(q) || lab.includes(q) || pc.includes(q);
      });
    }

    // Risk filter
    if (riskFilter !== "all") {
      arr = arr.filter(
        (r) => String(r.overallRisk || "").toLowerCase() === riskFilter,
      );
    }

    // Sort
    if (sortMode === "oldest") {
      arr.sort(
        (a, b) =>
          (a.uploadedAt?.toMillis?.() ?? 0) - (b.uploadedAt?.toMillis?.() ?? 0),
      );
    } else if (sortMode === "newest") {
      arr.sort(
        (a, b) =>
          (b.uploadedAt?.toMillis?.() ?? 0) - (a.uploadedAt?.toMillis?.() ?? 0),
      );
    } else if (sortMode === "highestRisk") {
      arr.sort((a, b) => safeScore(b) - safeScore(a));
    }

    return arr;
  }, [reports, search, riskFilter, sortMode]);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-12">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-start justify-between gap-3 flex-wrap mb-6">
            <div>
              <h1 className="text-3xl font-bold text-foreground">
                Your Report History
              </h1>
              <p className="text-muted-foreground mt-1">
                Search, filter, and open any report analysis.
              </p>
            </div>

            <Button onClick={() => navigate("/upload")}>
              <FileText className="mr-2 h-4 w-4" />
              Upload New Report
            </Button>
          </div>

          {/* Controls */}
          <Card className="mb-6">
            <CardContent className="pt-6">
              <div className="grid md:grid-cols-3 gap-3">
                <div className="relative">
                  <Search className="h-4 w-4 absolute left-3 top-3 text-muted-foreground" />
                  <Input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-9"
                    placeholder="Search by filename, lab, or condition..."
                  />
                </div>

                <div className="flex gap-2">
                  <Button
                    variant={riskFilter === "all" ? "default" : "outline"}
                    className="w-full"
                    onClick={() => setRiskFilter("all")}
                  >
                    All
                  </Button>
                  <Button
                    variant={riskFilter === "low" ? "default" : "outline"}
                    className="w-full"
                    onClick={() => setRiskFilter("low")}
                  >
                    Low
                  </Button>
                  <Button
                    variant={riskFilter === "moderate" ? "default" : "outline"}
                    className="w-full"
                    onClick={() => setRiskFilter("moderate")}
                  >
                    Moderate
                  </Button>
                  <Button
                    variant={riskFilter === "high" ? "default" : "outline"}
                    className="w-full"
                    onClick={() => setRiskFilter("high")}
                  >
                    High
                  </Button>
                </div>

                <div className="flex gap-2">
                  <Button
                    variant={sortMode === "newest" ? "default" : "outline"}
                    className="w-full"
                    onClick={() => setSortMode("newest")}
                  >
                    <ArrowDownWideNarrow className="mr-2 h-4 w-4" />
                    Newest
                  </Button>
                  <Button
                    variant={sortMode === "oldest" ? "default" : "outline"}
                    className="w-full"
                    onClick={() => setSortMode("oldest")}
                  >
                    <ArrowDownAZ className="mr-2 h-4 w-4" />
                    Oldest
                  </Button>
                  <Button
                    variant={sortMode === "highestRisk" ? "default" : "outline"}
                    className="w-full"
                    onClick={() => setSortMode("highestRisk")}
                  >
                    Highest Risk
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Loading */}
          {isLoading && (
            <div className="flex justify-center items-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="ml-2">Loading...</p>
            </div>
          )}

          {/* Empty */}
          {!isLoading && reports.length === 0 && (
            <Card>
              <CardContent className="py-12 text-center">
                <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  No Reports Yet
                </h3>
                <p className="text-muted-foreground mb-6">
                  Upload your first blood report to get started
                </p>
                <Button onClick={() => navigate("/upload")}>
                  Upload Report
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Results */}
          {!isLoading && filtered.length > 0 && (
            <div className="space-y-6">
              {filtered.map((report) => {
                const score = safeScore(report);
                const method =
                  report.extractionMethod ||
                  report.analysisData?.extraction?.method ||
                  "digital";
                const pages =
                  report.pagesProcessed ||
                  report.analysisData?.extraction?.pages ||
                  null;

                return (
                  <Card key={report.id}>
                    <CardHeader>
                      <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div>
                          <CardTitle className="text-xl">
                            {report.fileName || "Report Analysis"}
                          </CardTitle>

                          <CardDescription className="flex items-center gap-2 mt-2">
                            <Calendar className="h-4 w-4" />
                            Analyzed on: {formatDate(report.uploadedAt)}
                          </CardDescription>

                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span>
                              Extraction:{" "}
                              <span className="text-foreground font-medium">
                                {String(method).toUpperCase()}
                              </span>
                            </span>
                            <span>
                              Pages:{" "}
                              <span className="text-foreground font-medium">
                                {pages ?? "—"}
                              </span>
                            </span>
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-2 min-w-[180px]">
                          <Badge
                            variant={
                              riskVariant(
                                String(report.overallRisk || ""),
                              ) as any
                            }
                          >
                            {String(report.overallRisk || "Unknown")} Risk
                          </Badge>

                          <div className="w-full">
                            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                              <span>Score</span>
                              <span className="font-medium text-foreground">
                                {Math.round(score)}/100
                              </span>
                            </div>
                            <Progress value={scoreToProgress(score)} />
                          </div>
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent>
                      <div className="flex items-center justify-between text-sm text-muted-foreground mb-4 flex-wrap gap-3">
                        <div className="flex items-center gap-2">
                          <span>
                            Issues Found:{" "}
                            <span className="text-foreground font-medium">
                              {report.issuesFound ??
                                report.analysisData?.issuesFound ??
                                0}
                            </span>
                          </span>
                        </div>

                        <span>
                          Markers Checked:{" "}
                          <span className="text-foreground font-medium">
                            {report.markersChecked ??
                              report.analysisData?.markersChecked ??
                              0}
                          </span>
                        </span>
                      </div>

                      <div className="flex gap-2 flex-wrap">
                        <Button
                          onClick={() =>
                            navigate("/results", {
                              state: { reportData: report.analysisData },
                            })
                          }
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          View Analysis
                        </Button>

                        <Button variant="outline" disabled>
                          <Download className="mr-2 h-4 w-4" />
                          Download PDF (Soon)
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}
