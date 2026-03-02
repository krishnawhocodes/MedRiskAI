import { createContext, useContext, useEffect, useState } from "react";
import { type User } from "firebase/auth";
import { listenToAuthChanges } from "./firebase"; 

interface AuthContextType {
  user: User | null;
  userId: string | null;
  isAuthReady: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthReady, setIsAuthReady] = useState(false);

  useEffect(() => {
    const unsubscribe = listenToAuthChanges((user) => {
      setUser(user);
      setIsAuthReady(true);
    });
    return () => unsubscribe();
  }, []);

  const value = {
    user,
    userId: user?.uid || null,
    isAuthReady,
  };

  return (
    <AuthContext.Provider value={value}>
      {isAuthReady ? children : <div>Loading App...</div>}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
