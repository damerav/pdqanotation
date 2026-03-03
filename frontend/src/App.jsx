import { useState } from "react";
import { Amplify } from "aws-amplify";
import { Authenticator } from "@aws-amplify/ui-react";
import "@aws-amplify/ui-react/styles.css";
import awsConfig from "./utils/aws-config";
import UploadPage from "./pages/UploadPage";
import HistoryPage from "./pages/HistoryPage";
import "./App.css";

Amplify.configure(awsConfig);

export default function App() {
  return (
    <Authenticator loginMechanisms={["email"]} variation="modal">
      {({ signOut, user }) => <Shell user={user} signOut={signOut} />}
    </Authenticator>
  );
}

function Shell({ user, signOut }) {
  const [page, setPage] = useState("upload");
  const email = user?.signInDetails?.loginId ?? "";

  return (
    <div className="app-shell">
      <nav className="topnav">
        <span className="brand">Email Annotator</span>
        <div className="nav-links">
          <button className={`nav-btn ${page === "upload" ? "active" : ""}`} onClick={() => setPage("upload")}>
            New Job
          </button>
          <button className={`nav-btn ${page === "history" ? "active" : ""}`} onClick={() => setPage("history")}>
            History
          </button>
        </div>
        <div className="nav-user">
          <span className="user-email">{email}</span>
          <button className="signout-btn" onClick={signOut}>Sign Out</button>
        </div>
      </nav>

      <main className="main-content">
        {page === "upload"
          ? <UploadPage userEmail={email} />
          : <HistoryPage userEmail={email} />
        }
      </main>
    </div>
  );
}
