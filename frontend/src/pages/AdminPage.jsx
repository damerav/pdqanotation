import { useState, useEffect } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import awsConfig from "../utils/aws-config";

const API_BASE = awsConfig.API.REST.EmailAnnotatorAPI.endpoint;

export default function AdminPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [newPassword, setNewPassword] = useState("Welcome@123");
  const [creating, setCreating] = useState(false);
  const [actionMsg, setActionMsg] = useState("");

  useEffect(() => { loadUsers(); }, []);

  async function getToken() {
    const session = await fetchAuthSession();
    return session.tokens.idToken.toString();
  }

  async function loadUsers() {
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      const resp = await fetch(`${API_BASE}/admin/users`, {
        headers: { Authorization: token },
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Failed to load users");
      setUsers(data.users || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateUser(e) {
    e.preventDefault();
    setCreating(true);
    setActionMsg("");
    try {
      const token = await getToken();
      const resp = await fetch(`${API_BASE}/admin/users`, {
        method: "POST",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({
          email: newEmail, role: newRole, temp_password: newPassword,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Failed to create user");
      setActionMsg(data.message);
      setNewEmail("");
      setShowCreate(false);
      loadUsers();
    } catch (err) {
      setActionMsg(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteUser(username) {
    if (!confirm(`Delete user ${username}? This cannot be undone.`)) return;
    setActionMsg("");
    try {
      const token = await getToken();
      const resp = await fetch(`${API_BASE}/admin/users`, {
        method: "DELETE",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Failed to delete user");
      setActionMsg(data.message);
      loadUsers();
    } catch (err) {
      setActionMsg(err.message);
    }
  }

  async function handleToggleRole(username, currentRole) {
    const newRole = currentRole === "admin" ? "user" : "admin";
    setActionMsg("");
    try {
      const token = await getToken();
      const resp = await fetch(`${API_BASE}/admin/users/role`, {
        method: "POST",
        headers: { Authorization: token, "Content-Type": "application/json" },
        body: JSON.stringify({ username, role: newRole }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Failed to update role");
      setActionMsg(data.message);
      loadUsers();
    } catch (err) {
      setActionMsg(err.message);
    }
  }

  return (
    <div>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
          <div>
            <h2>User Management</h2>
            <p className="subtitle" style={{ marginBottom: 0 }}>
              Add, remove, and manage user roles
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button onClick={() => setShowCreate(!showCreate)} style={{
              background: "#e94560", color: "white", border: "none",
              borderRadius: "7px", padding: "0.45rem 1rem",
              cursor: "pointer", fontSize: "0.85rem", fontWeight: 600,
            }}>
              + Add User
            </button>
            <button onClick={loadUsers} style={{
              background: "transparent", border: "1px solid #d1d5db",
              borderRadius: "7px", padding: "0.4rem 0.9rem",
              cursor: "pointer", fontSize: "0.85rem", color: "#374151",
            }}>
              ↻ Refresh
            </button>
          </div>
        </div>

        {actionMsg && (
          <div className="status-banner success" style={{ marginBottom: "1rem" }}>
            {actionMsg}
          </div>
        )}

        {showCreate && (
          <form onSubmit={handleCreateUser} style={{
            background: "#f9fafb", border: "1px solid #e5e7eb",
            borderRadius: "10px", padding: "1.25rem", marginBottom: "1.25rem",
          }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Email</label>
                <input type="email" value={newEmail} required
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="user@company.com" />
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Temporary Password</label>
                <input type="text" value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)} />
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginTop: "0.75rem" }}>
              <label style={{ fontSize: "0.85rem", fontWeight: 500 }}>Role:</label>
              <label style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                <input type="radio" name="role" value="user"
                  checked={newRole === "user"} onChange={() => setNewRole("user")} />
                User
              </label>
              <label style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                <input type="radio" name="role" value="admin"
                  checked={newRole === "admin"} onChange={() => setNewRole("admin")} />
                Admin
              </label>
              <button type="submit" disabled={creating} style={{
                marginLeft: "auto", background: "#166534", color: "white",
                border: "none", borderRadius: "6px", padding: "0.4rem 1rem",
                cursor: "pointer", fontSize: "0.85rem", fontWeight: 600,
              }}>
                {creating ? "Creating…" : "Create User"}
              </button>
              <button type="button" onClick={() => setShowCreate(false)} style={{
                background: "transparent", border: "1px solid #d1d5db",
                borderRadius: "6px", padding: "0.4rem 0.75rem",
                cursor: "pointer", fontSize: "0.85rem", color: "#6b7280",
              }}>
                Cancel
              </button>
            </div>
          </form>
        )}

        {loading && <p className="empty-state">Loading users…</p>}
        {error && <p className="empty-state" style={{ color: "#991b1b" }}>{error}</p>}

        {!loading && !error && users.length > 0 && (
          <table className="history-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username}>
                  <td style={{ fontWeight: 500 }}>{u.email || u.username}</td>
                  <td>
                    <span className={`badge ${u.role === "admin" ? "processing" : "done"}`}>
                      {u.role}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontSize: "0.8rem", color: u.status === "CONFIRMED" ? "#166534" : "#92400e" }}>
                      {u.status}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.82rem", color: "#6b7280" }}>
                    {new Date(u.created).toLocaleDateString()}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button onClick={() => handleToggleRole(u.username, u.role)} style={{
                      background: "transparent", border: "1px solid #d1d5db",
                      borderRadius: "5px", padding: "0.25rem 0.6rem",
                      cursor: "pointer", fontSize: "0.78rem", marginRight: "0.4rem",
                    }}>
                      {u.role === "admin" ? "→ User" : "→ Admin"}
                    </button>
                    <button onClick={() => handleDeleteUser(u.username)} style={{
                      background: "transparent", border: "1px solid #fecaca",
                      borderRadius: "5px", padding: "0.25rem 0.6rem",
                      cursor: "pointer", fontSize: "0.78rem", color: "#991b1b",
                    }}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!loading && !error && users.length === 0 && (
          <p className="empty-state">No users found.</p>
        )}
      </div>
    </div>
  );
}
