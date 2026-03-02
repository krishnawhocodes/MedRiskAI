import { Link } from "react-router-dom";
import { Activity } from "lucide-react";

const Footer = () => {
  return (
    <footer className="border-t bg-background">
      <div className="container mx-auto px-4 py-8">
        <div className="flex flex-col md:flex-row justify-between items-center">
          <div className="flex items-center gap-2 mb-4 md:mb-0">
            <Activity className="h-6 w-6 text-primary" />
            <span className="text-xl font-bold text-foreground">
              MedRisk <span className="text-primary">AI</span>
            </span>
          </div>
          <div className="flex gap-4 mb-4 md:mb-0">
            <Link
              to="/upload"
              className="text-sm text-muted-foreground hover:text-primary"
            >
              Upload
            </Link>
            <Link
              to="/history"
              className="text-sm text-muted-foreground hover:text-primary"
            >
              History
            </Link>
            <Link
              to="/find-doctor"
              className="text-sm text-muted-foreground hover:text-primary"
            >
              Find Doctor
            </Link>
          </div>
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} MedRisk AI. All rights reserved.
          </p>
        </div>
        <p className="text-xs text-muted-foreground/50 mt-4 text-center">
          Disclaimer: MedRisk AI is for informational purposes only. Always
          consult a certified medical professional.
        </p>
      </div>
    </footer>
  );
};

export default Footer;