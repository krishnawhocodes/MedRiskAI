import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { User as UserIcon } from "lucide-react";
import Navbar from "../components/Navbar"; // <-- FIXED PATH
import Footer from "../components/Footer"; // <-- FIXED PATH
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "./AuthContext";
import { updateProfile } from "firebase/auth";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const Profile = () => {
  const { toast } = useToast();
  const { user } = useAuth();

  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
  });
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (user) {
      setFormData({
        fullName: user.displayName || "",
        email: user.email || "",
      });
    }
  }, [user]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;

    setIsLoading(true);
    try {
      await updateProfile(user, {
        displayName: formData.fullName,
      });
      toast({
        title: "Profile Updated",
        description: "Your profile has been successfully updated",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Could not update your profile.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteAccount = () => {
    // TODO: Implement actual account deletion logic
    console.log("Account deletion requested");
    toast({
      title: "Action Not Implemented",
      description: "Account deletion is not yet available.",
    });
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar /> {/* <-- FIXED: Props removed. */}
      <main className="flex-1 container mx-auto px-4 py-12">
        <div className="max-w-2xl mx-auto space-y-8">
          <h1 className="text-3xl font-bold text-foreground">
            Account Settings
          </h1>

          {/* Profile Card */}
          <Card>
            <CardHeader>
              <CardTitle>Public Profile</CardTitle>
              <CardDescription>
                This is how other users will see you on the site
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSaveProfile} className="space-y-6">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center">
                    <UserIcon className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <Button variant="outline" type="button" disabled>
                    Upload Photo (Soon)
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="fullName">Full Name</Label>
                  <Input
                    id="fullName"
                    value={formData.fullName}
                    onChange={(e) =>
                      setFormData({ ...formData, fullName: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={formData.email}
                    disabled
                  />
                  <p className="text-sm text-muted-foreground">
                    Email address cannot be changed.
                  </p>
                </div>

                <Button type="submit" disabled={isLoading}>
                  {isLoading ? "Saving..." : "Save Changes"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Separator />

          {/* Delete Account Card */}
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="text-destructive">Delete Account</CardTitle>
              <CardDescription>
                Irreversible actions that will permanently affect your account
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive">Delete Account</Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>
                      Are you absolutely sure?
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      This action cannot be undone. This will permanently delete
                      your account and remove all your data from our servers.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDeleteAccount}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Delete Account
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </CardContent>
          </Card>
        </div>
      </main>
      <Footer />
    </div>
  );
};
export default Profile;
