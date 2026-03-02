import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Upload as UploadIcon, FileText, X, Loader2 } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { useToast } from "@/hooks/use-toast";
import { Progress } from "@/components/ui/progress";
import { db, appId } from "./firebase";
import { useAuth } from "./AuthContext";
import { collection, addDoc, serverTimestamp } from "firebase/firestore";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

function isProbablyPdf(file: File): boolean {
  const nameOk = file.name?.toLowerCase().endsWith(".pdf");
  const type = (file.type || "").toLowerCase();

  // browsers sometimes send: "", "application/octet-stream", "application/x-pdf"
  const typeOk =
    type === "application/pdf" ||
    type === "application/x-pdf" ||
    type === "application/octet-stream" ||
    type.includes("pdf");

  return Boolean(nameOk || typeOk);
}

async function safeReadError(response: Response): Promise<string> {
  try {
    const ct = (response.headers.get("content-type") || "").toLowerCase();
    if (ct.includes("application/json")) {
      const j = await response.json();
      return j?.detail || j?.message || JSON.stringify(j);
    }
    const t = await response.text();
    return t || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

function formatMB(bytes: number) {
  return (bytes / (1024 * 1024)).toFixed(2);
}

const Upload = () => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [statusText, setStatusText] = useState<string>("");

  const { userId } = useAuth();

  const fileSizeText = useMemo(() => {
    if (!selectedFile) return "";
    return `${formatMB(selectedFile.size)} MB`;
  }, [selectedFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file && isProbablyPdf(file)) {
        setSelectedFile(file);
        return;
      }
      toast({
        title: "Invalid File",
        description: "Please upload a PDF file only",
        variant: "destructive",
      });
    },
    [toast],
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && isProbablyPdf(file)) {
      setSelectedFile(file);
      return;
    }
    toast({
      title: "Invalid File",
      description: "Please upload a PDF file only",
      variant: "destructive",
    });
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    if (!userId) {
      toast({
        title: "Error",
        description: "You must be logged in.",
        variant: "destructive",
      });
      return;
    }

    setIsUploading(true);
    setUploadProgress(10);
    setStatusText("Uploading PDF...");

    const formData = new FormData();
    formData.append("file", selectedFile);

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 120_000); // 2 min

    try {
      const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      setUploadProgress(40);
      setStatusText("Extracting biomarkers (OCR auto if needed)...");

      if (!response.ok) {
        const msg = await safeReadError(response);
        throw new Error(msg || "Upload failed");
      }

      setUploadProgress(70);
      setStatusText("Predicting risks & building recommendations...");

      const analysisResult = await response.json();

      setUploadProgress(90);
      setStatusText("Saving report to history...");

      // Save to Firestore (History/Dashboard depends on this)
      const reportsCollectionPath = `artifacts/${appId}/users/${userId}/reports`;

      await addDoc(collection(db, reportsCollectionPath), {
        analysisData: analysisResult,
        fileName: selectedFile.name,
        uploadedAt: serverTimestamp(),
        overallRisk: analysisResult?.overallRisk ?? "Unknown",
        primaryCondition: analysisResult?.primaryCondition ?? "General Health",
        issuesFound: analysisResult?.issuesFound ?? 0,
        markersChecked: analysisResult?.markersChecked ?? 0,

        extractionMethod: analysisResult?.extraction?.method ?? "unknown",
        pagesProcessed: analysisResult?.extraction?.pages ?? null,
      });

      setUploadProgress(100);
      setStatusText("Done!");

      // Show OCR/Extraction note
      const method = String(
        analysisResult?.extraction?.method || "",
      ).toLowerCase();
      if (method === "ocr" || method === "mixed") {
        toast({
          title: "OCR Was Used ✅",
          description:
            method === "mixed"
              ? "Some pages were scanned, OCR was applied where needed."
              : "This report was scanned. OCR extraction was used.",
        });
      }

      // Show warnings if backend returns any
      const warnings = analysisResult?.extraction?.warnings;
      if (Array.isArray(warnings) && warnings.length > 0) {
        toast({
          title: "Extraction Notes",
          description: warnings.slice(0, 2).join(" • "),
        });
      }

      toast({
        title: "Analysis Complete",
        description: "Report analyzed and saved to your history.",
      });

      window.setTimeout(() => {
        navigate("/results", { state: { reportData: analysisResult } });
      }, 500);
    } catch (error) {
      const msg =
        error instanceof DOMException && error.name === "AbortError"
          ? "Request timed out. Please try again (or use a smaller/clearer PDF)."
          : (error as Error)?.message || "Please try again.";

      toast({
        title: "An Error Occurred",
        description: msg,
        variant: "destructive",
      });

      setUploadProgress(0);
      setStatusText("");
      setIsUploading(false);
    } finally {
      window.clearTimeout(timeout);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-12 flex items-center justify-center">
        <div className="w-full max-w-2xl">
          <h1 className="text-3xl font-bold text-center mb-2">
            Upload Your Blood Report
          </h1>
          <p className="text-center text-muted-foreground mb-8">
            Works with digital PDFs and scanned reports (OCR runs
            automatically).
          </p>

          <Card>
            <CardContent className="p-6">
              {!selectedFile ? (
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() =>
                    document.getElementById("file-upload")?.click()
                  }
                  className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors duration-200 ${
                    isDragging
                      ? "border-primary bg-primary/10"
                      : "border-muted-foreground/30 hover:border-primary/50"
                  }`}
                >
                  <UploadIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="font-semibold text-foreground">
                    Drag & drop your PDF here
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    or click to browse files
                  </p>

                  <p className="text-xs text-muted-foreground mt-4">
                    Tip: If your report is scanned/blurry, OCR will
                    auto-activate ✅
                  </p>

                  <input
                    id="file-upload"
                    type="file"
                    accept="application/pdf"
                    className="hidden"
                    onChange={handleFileChange}
                  />
                </div>
              ) : (
                <div className="flex items-center justify-between p-4 bg-accent rounded-lg">
                  <div className="flex items-center gap-3">
                    <FileText className="h-6 w-6 text-primary" />
                    <div>
                      <p className="font-medium text-foreground">
                        {selectedFile.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {fileSizeText} • PDF
                      </p>
                    </div>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => setSelectedFile(null)}
                    disabled={isUploading}
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </div>
              )}

              {/* Progress UI */}
              {isUploading && (
                <div className="mt-5 space-y-2">
                  <Progress value={uploadProgress} />
                  <p className="text-xs text-muted-foreground">{statusText}</p>
                </div>
              )}

              <div className="mt-6 flex gap-3">
                <Button
                  className="w-full"
                  onClick={handleUpload}
                  disabled={!selectedFile || isUploading}
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    "Upload & Analyze"
                  )}
                </Button>

                <Button
                  className="w-full"
                  variant="outline"
                  onClick={() => navigate("/dashboard")}
                  disabled={isUploading}
                >
                  Back to Dashboard
                </Button>
              </div>

              <div className="mt-6 text-xs text-muted-foreground">
                <p className="font-medium text-foreground mb-1">Notes:</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>OCR is automatic when the PDF text is low quality.</li>
                  <li>
                    For best extraction, upload a sharp/clear lab report PDF.
                  </li>
                  <li>
                    If you get “No biomarkers found”, try another PDF scan
                    quality.
                  </li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Upload;
