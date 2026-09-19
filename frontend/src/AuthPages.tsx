import { useEffect, useState } from "react";
import "./App.css";
const API = import.meta.env.VITE_API_URL || "/api/v1";
export type Auth = {
  user: { id: string; name: string; email: string; role: string };
  accessToken: string;
  refreshToken: string;
};
type Invite = { email: string; role: string };
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!r.ok) {
    const x = await r.json().catch(() => ({ message: "Request failed" }));
    throw new Error(x.message || x.detail || "Request failed");
  }
  return r.json();
}
export function saveAuth(a: Auth, set: (a: Auth) => void) {
  sessionStorage.setItem("auth", JSON.stringify(a));
  sessionStorage.setItem("accessToken", a.accessToken);
  set(a);
}
function go(path: string) {
  location.href = path;
}
export function RoleLanding({ onLogin }: { onLogin: (a: Auth) => void }) {
  const [role, setRole] = useState("student");
  return (
    <div className="auth-layout">
      <section className="auth-story">
        <div className="brandmark">B</div>
        <span className="eyebrow">BARABARI COLLECTIVE</span>
        <h1>
          Your project journey,
          <br />
          with the right guidance.
        </h1>
        <p>
          Understand requirements, resolve blockers independently, and reach
          mentors when human judgment matters.
        </p>
        <div className="role-cards">
          {["student", "core_reviewer"].map((r) => (
            <button
              className={role === r ? "selected" : ""}
              onClick={() => setRole(r)}
              key={r}
            >
              <b>{r}</b>
              <span>
                {r === "student"
                  ? "Projects, guided RAG and blockers"
                  : "Core team triage and project decisions"}
              </span>
            </button>
          ))}
        </div>
        <button className="admin-link" onClick={() => go("/admin/login")}>
          Barabari administrator sign in
        </button>
      </section>
      <RoleLogin expectedRole={role} onLogin={onLogin} />
    </div>
  );
}
export function InviteRegistration({
  token,
  onLogin,
}: {
  token: string;
  onLogin: (a: Auth) => void;
}) {
  const [invite, setInvite] = useState<Invite | null>(null),
    [error, setError] = useState(""),
    [name, setName] = useState(""),
    [password, setPassword] = useState(""),
    [confirm, setConfirm] = useState(""),
    [primaryCategory, setPrimaryCategory] = useState("Developer"),
    [categories, setCategories] = useState("Developer"),
    [skills, setSkills] = useState(""),
    [capacity, setCapacity] = useState(5);

  useEffect(() => {
    api<Invite>("/invitations/" + token)
      .then(setInvite)
      .catch((e) => {
        const saved = sessionStorage.getItem("auth");
        if (saved && JSON.parse(saved).user.role !== "core_admin") {
          location.replace("/");
          return;
        }
        setError(e.message);
      });
  }, [token]);

  if (error) return <Message title="Invitation unavailable" copy={error} />;
  if (!invite)
    return (
      <Message
        title="Validating invitation"
        copy="Checking your secure invitation…"
      />
    );

  const isMentor = invite.role === "core_reviewer";

  return (
    <div className="login-page">
      <form
        className="login-card"
        onSubmit={async (e) => {
          e.preventDefault();
          if (password !== confirm) {
            setError("Passwords do not match");
            return;
          }
          const payload: Record<string, any> = { name, password };
          if (isMentor) {
            const catList = categories
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean);
            const skillList = skills
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean);
            if (!skillList.length) {
              setError("Please enter at least one skill.");
              return;
            }
            payload.primary_category = primaryCategory;
            payload.categories = catList.length ? catList : [primaryCategory];
            payload.skills = skillList;
            payload.max_capacity = capacity;
          }
          try {
            onLogin(
              await api<Auth>("/invitations/" + token + "/accept", {
                method: "POST",
                body: JSON.stringify(payload),
              }),
            );
          } catch (x) {
            setError(x instanceof Error ? x.message : "Registration failed");
          }
        }}
      >
        <div className="brandmark">B</div>
        <span className="eyebrow">INVITATION VERIFIED</span>
        <h1>
          Join as {isMentor ? "Core Reviewer" : invite.role.toLowerCase()}
        </h1>
        <p>
          {invite.email}
          <br />
          Your invitation determines this role.
        </p>
        <label>
          Full name
          <input
            required
            placeholder="Your full name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        {isMentor && (
          <>
            <label>
              Primary domain / track
              <select
                value={primaryCategory}
                onChange={(e) => {
                  const val = e.target.value;
                  setPrimaryCategory(val);
                  if (!categories || categories === primaryCategory) {
                    setCategories(val);
                  }
                }}
              >
                <option>Developer</option>
                <option>Tester</option>
                <option>DevOps Engineer</option>
                <option>Network Engineer</option>
                <option>UI/UX Designer</option>
                <option>Data Engineer</option>
              </select>
            </label>
            <label>
              Categories (comma separated)
              <input
                required
                placeholder="Developer, Backend, Cloud..."
                value={categories}
                onChange={(e) => setCategories(e.target.value)}
              />
            </label>
            <label>
              Skills & technologies (comma separated)
              <input
                required
                placeholder="React, Java, AWS, Python..."
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
              />
            </label>
            <label>
              Mentoring capacity (max active tickets)
              <input
                type="number"
                min={1}
                max={50}
                required
                value={capacity}
                onChange={(e) => setCapacity(Number(e.target.value))}
              />
            </label>
          </>
        )}
        <label>
          Create password
          <input
            required
            minLength={10}
            type="password"
            placeholder="At least 10 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <label>
          Confirm password
          <input
            required
            type="password"
            placeholder="Confirm password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="primary">Verify & create account</button>
      </form>
    </div>
  );
}
export function ForgotPassword() {
  const [email, setEmail] = useState(""),
    [message, setMessage] = useState("");
  return (
    <div className="login-page">
      <form
        className="login-card"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            setMessage(
              (
                await api<{ message: string }>("/auth/forgot-password", {
                  method: "POST",
                  body: JSON.stringify({ email }),
                })
              ).message,
            );
          } catch (x) {
            setMessage(String(x));
          }
        }}
      >
        <div className="brandmark">B</div>
        <h1>Forgot password</h1>
        <p>We will send a single-use reset link to a registered account.</p>
        <label>
          Email
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        {message && <div className="answer">{message}</div>}
        <button className="primary">Send reset link</button>
        <button type="button" className="text-btn" onClick={() => go("/")}>
          Back to sign in
        </button>
      </form>
    </div>
  );
}
export function ResetPassword() {
  const token = new URLSearchParams(location.search).get("token") || "";
  const [p, setP] = useState(""),
    [c, setC] = useState(""),
    [message, setMessage] = useState("");
  return (
    <div className="login-page">
      <form
        className="login-card"
        onSubmit={async (e) => {
          e.preventDefault();
          if (p !== c) {
            setMessage("Passwords do not match");
            return;
          }
          try {
            setMessage(
              (
                await api<{ message: string }>("/auth/reset-password", {
                  method: "POST",
                  body: JSON.stringify({ token, password: p }),
                })
              ).message,
            );
          } catch (x) {
            setMessage(String(x));
          }
        }}
      >
        <div className="brandmark">B</div>
        <h1>Set a new password</h1>
        <label>
          New password
          <input
            required
            minLength={10}
            type="password"
            value={p}
            onChange={(e) => setP(e.target.value)}
          />
        </label>
        <label>
          Confirm password
          <input
            required
            type="password"
            value={c}
            onChange={(e) => setC(e.target.value)}
          />
        </label>
        {message && <div className="answer">{message}</div>}
        <button className="primary">Update password</button>
      </form>
    </div>
  );
}
export function RoleLogin({
  onLogin,
  expectedRole,
}: {
  onLogin: (a: Auth) => void;
  expectedRole?: string;
}) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState("");
  return (
    <div className="login-page embedded">
      <form
        className="login-card"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            const a = await api<Auth>("/auth/login", {
              method: "POST",
              body: JSON.stringify({ email, password }),
            });
            if (expectedRole && a.user.role !== expectedRole)
              throw new Error(
                "This account belongs to a different role portal.",
              );
            onLogin(a);
          } catch (x) {
            setError(x instanceof Error ? x.message : "Login failed");
          }
        }}
      >
        <span className="eyebrow">{expectedRole || "MEMBER"} PORTAL</span>
        <h1>Welcome back</h1>
        <label>
          Email
          <input
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
          />
        </label>
        <label>
          Password
          <input
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
          />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="primary">Sign in securely</button>
        <button
          type="button"
          className="text-btn"
          onClick={() => go("/forgot-password")}
        >
          Forgot password?
        </button>
      </form>
    </div>
  );
}
function Message({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brandmark">B</div>
        <h1>{title}</h1>
        <p>{copy}</p>
      </div>
    </div>
  );
}
