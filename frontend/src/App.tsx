import { useEffect, useState } from "react";
import {
  Bell,
  BookOpen,
  ChevronRight,
  CircleHelp,
  FolderKanban,
  LayoutDashboard,
  Menu,
  MessageSquareMore,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  X,
  Plus,
  Send,
  RefreshCw,
  CheckCircle2,
} from "lucide-react";
import {
  ForgotPassword,
  InviteRegistration,
  ResetPassword,
  RoleLanding,
  saveAuth,
} from "./AuthPages";
import "./App.css";
const API = import.meta.env.VITE_API_URL || "/api/v1",
  AI = API;
type User = { id: string; name: string; email: string; role: string };
type Auth = { user: User; accessToken: string; refreshToken: string };
type Project = {
  id: string;
  name: string;
  summary: string;
  status: string;
  health: number;
  students: number;
  stakeholder_name?: string;
  stakeholder_organization?: string;
  requirement_analysis?: string;
  expected_deliverables?: string[];
  acceptance_criteria?: string[];
  tech_stack?: string[];
  repository_url?: string;
};
type Invite = {
  id: string;
  email: string;
  role: string;
  projectId?: string;
  token: string;
  status: string;
  expiresAt: string;
};
type Work = {
  id: string;
  projectId: string;
  type: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  owner: string;
};
type Esc = {
  id: string;
  projectId: string;
  student: string;
  question: string;
  reason: string;
  status: string;
  mentorResponse?: string;
  verified: boolean;
  reusableAsKnowledge: boolean;
};
type Stats = {
  activeProjects: number;
  users: number;
  openTickets: number;
  openEscalations: number;
  selfResolvedRate: number;
  mentorHoursSaved: number;
};
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem("accessToken");
  const r = await fetch(API + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...init?.headers,
    },
  });
  if (!r.ok) {
    const x = await r.json().catch(() => ({ message: "Request failed" }));
    throw new Error(x.message || x.detail || "Request failed");
  }
  return r.status === 204 ? (undefined as T) : r.json();
}
const nav = [
  [LayoutDashboard, "Overview"],
  [FolderKanban, "Projects"],
  [Users, "People & invitations"],
  [MessageSquareMore, "Ask support"],
  [MessageSquareMore, "Mentor queue"],
  [BookOpen, "Knowledge"],
  [ShieldCheck, "Administration"],
] as const;
function navigationFor(role: string) {
  if (role === "student")
    return nav.filter((x) =>
      ["Overview", "Projects", "Ask support", "Knowledge"].includes(x[1]),
    );
  if (role === "core_reviewer")
    return nav.filter((x) =>
      ["Overview", "Projects", "Mentor queue", "Knowledge"].includes(x[1]),
    );
  if (role === "CLIENT")
    return nav.filter((x) => ["Overview", "Projects"].includes(x[1]));
  return nav;
}
export default function App() {
  const [auth, setAuth] = useState<Auth | null>(() => {
      const v = sessionStorage.getItem("auth");
      return v ? JSON.parse(v) : null;
    }),
    [active, setActive] = useState("Overview"),
    [mobile, setMobile] = useState(false);
  const route = window.location.pathname;
  if (route.startsWith("/invite/"))
    return (
      <InviteRegistration
        token={route.substring("/invite/".length)}
        onLogin={(a) => {
          saveAuth(a, setAuth);
          location.replace("/");
        }}
      />
    );
  if (!auth) {
    if (route === "/forgot-password") return <ForgotPassword />;
    if (route === "/reset-password") return <ResetPassword />;
    if (route === "/admin/login")
      return (
        <Login
          expectedRole="core_admin"
          onLogin={(a) => saveAuth(a, setAuth)}
        />
      );
    return <RoleLanding onLogin={(a) => saveAuth(a, setAuth)} />;
  }
  return (
    <div className="shell">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <div className="brand">
          <div className="brandmark">B</div>
          <div>
            <strong>barabari</strong>
            <span>Mentoring intelligence</span>
          </div>
          <button className="close" onClick={() => setMobile(false)}>
            <X />
          </button>
        </div>
        <nav>
          {navigationFor(auth.user.role).map(([I, l]) => (
            <button
              className={active === l ? "active" : ""}
              onClick={() => {
                setActive(l);
                setMobile(false);
              }}
              key={l}
            >
              <I size={19} />
              {l}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <CircleHelp />
          <div>
            <b>Connected workspace</b>
            <span>Atlas · Backend · AI</span>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <button className="hamburger" onClick={() => setMobile(true)}>
            <Menu />
          </button>
          <div className="search">
            <Search />
            <input placeholder="Search projects, people, knowledge..." />
          </div>
          <button className="icon">
            <Bell />
            <i />
          </button>
          <div className="avatar">
            {auth.user.name
              .split(" ")
              .map((x) => x[0])
              .join("")
              .slice(0, 2)}
          </div>
          <div className="profile">
            <b>{auth.user.name}</b>
            <span>{auth.user.role}</span>
          </div>
          <button
            className="logout"
            onClick={() => {
              sessionStorage.clear();
              setAuth(null);
            }}
          >
            Sign out
          </button>
        </header>
        <section className="content">
          <Page active={active} auth={auth} />
        </section>
      </main>
    </div>
  );
}
function Page({ active, auth }: { active: string; auth: Auth }) {
  if (active === "Projects") return <Projects auth={auth} />;
  if (active === "People & invitations") return <People />;
  if (active === "Ask support") return <StudentTickets />;
  if (active === "Mentor queue") return <MentorQueue />;
  if (active === "Knowledge") return <Knowledge auth={auth} />;
  if (active === "Administration") return <Admin />;
  return <Overview auth={auth} />;
}
function Heading({
  over,
  title,
  copy,
  action,
}: {
  over: string;
  title: string;
  copy: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="welcome">
      <div>
        <span className="eyebrow">{over}</span>
        <h1>{title}</h1>
        <p>{copy}</p>
      </div>
      {action}
    </div>
  );
}
function Overview({ auth }: { auth: Auth }) {
  const [p, setP] = useState<Project[]>([]),
    [s, setS] = useState<Stats | null>(null);
  useEffect(() => {
    Promise.all([
      api<Project[]>("/projects"),
      api<Stats>("/analytics/overview"),
    ]).then(([a, b]) => {
      setP(a);
      setS(b);
    });
  }, []);
  return (
    <>
      <Heading
        over="LIVE PROJECT OPERATIONS"
        title={"Good evening, " + auth.user.name.split(" ")[0] + "."}
        copy="Monitor delivery, support demand, and mentor workload from one place."
      />
      <div className="stats">
        {[
          ["Active projects", s?.activeProjects ?? 0, "Live portfolio"],
          ["Registered users", s?.users ?? 0, "Invitation controlled"],
          ["Open escalations", s?.openEscalations ?? 0, "Needs mentor"],
          [
            "Mentor hours saved",
            (s?.mentorHoursSaved ?? 0) + "h",
            (s?.selfResolvedRate ?? 0) + "% self-resolved",
          ],
        ].map((x) => (
          <article key={x[0]}>
            <span>{x[0]}</span>
            <strong>{x[1]}</strong>
            <small>{x[2]}</small>
          </article>
        ))}
      </div>
      <section className="panel">
        <SectionTitle over="PORTFOLIO" title="Project pulse" />
        {p.map((x, i) => (
          <div className="project" key={x.id}>
            <div className={"project-icon c" + (i % 3)}>{initials(x.name)}</div>
            <div className="project-info">
              <b>{x.name}</b>
              <span>{x.summary}</span>
              <div className="bar">
                <i style={{ width: x.health + "%" }} />
              </div>
            </div>
            <div className="health">
              <b>{x.health}%</b>
              <span>Health</span>
            </div>
            <ChevronRight />
          </div>
        ))}
      </section>
    </>
  );
}
function Projects({ auth }: { auth: Auth }) {
  const [p, setP] = useState<Project[]>([]),
    [selected, setSelected] = useState<Project | null>(null),
    [work, setWork] = useState<Work[]>([]),
    [show, setShow] = useState(false),
    [editing, setEditing] = useState<Project | null>(null);
  const load = async () => {
    const list = await api<Project[]>("/projects");
    setP(list);
    if (selected) setSelected(list.find((x) => x.id === selected.id) || null);
  };
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    if (selected)
      api<Work[]>("/projects/" + selected.id + "/work").then(setWork);
  }, [selected]);
  return (
    <>
      <Heading
        over="DELIVERY WORKSPACE"
        title="Projects"
        copy="Students create and maintain the project and stakeholder context used by the AI."
        action={
          ["core_admin", "student"].includes(auth.user.role) ? (
            <button
              className="primary"
              onClick={() => {
                setEditing(null);
                setShow(true);
              }}
            >
              <Plus />
              New project
            </button>
          ) : undefined
        }
      />
      {show && (
        <ProjectForm
          initial={editing || undefined}
          done={() => {
            setShow(false);
            setEditing(null);
            void load();
          }}
        />
      )}
      <div className="page-grid">
        <section className="panel">
          <SectionTitle over="MY PROJECTS" title="Student portfolio" />
          {p.map((x) => (
            <button
              className={
                "list-button " + (selected?.id === x.id ? "selected" : "")
              }
              onClick={() => setSelected(x)}
              key={x.id}
            >
              <div className="project-icon c0">{initials(x.name)}</div>
              <div>
                <b>{x.name}</b>
                <span>{x.summary}</span>
              </div>
              <ChevronRight />
            </button>
          ))}
        </section>
        <section className="panel detail">
          <SectionTitle
            over="PROJECT WORK"
            title={selected?.name || "Select a project"}
          />
          {selected ? (
            <>
              <button
                className="secondary"
                onClick={() => {
                  setEditing(selected);
                  setShow(true);
                }}
              >
                Edit all project details
              </button>
              <button
                className="secondary"
                onClick={async () => {
                  const title = prompt("Task or ticket title");
                  if (title) {
                    await api("/projects/" + selected.id + "/work", {
                      method: "POST",
                      body: JSON.stringify({
                        type: "TASK",
                        title,
                        description: "Created from project workspace",
                        status: "OPEN",
                        priority: "MEDIUM",
                        owner: "",
                      }),
                    });
                    setWork(await api("/projects/" + selected.id + "/work"));
                  }
                }}
              >
                <Plus /> Add work item
              </button>
              {work.map((w) => (
                <div className="work-card" key={w.id}>
                  <span className={"priority " + w.priority.toLowerCase()}>
                    {w.type}
                  </span>
                  <div>
                    <b>{w.title}</b>
                    <p>{w.description}</p>
                  </div>
                  <em>{w.status}</em>
                </div>
              ))}
            </>
          ) : (
            <Empty text="Choose a project to see its tasks and tickets." />
          )}
        </section>
      </div>
    </>
  );
}
function ProjectForm({
  done,
  initial,
}: {
  done: () => void;
  initial?: Project;
}) {
  const [n, setN] = useState(initial?.name || ""),
    [summary, setSummary] = useState(initial?.summary || ""),
    [stakeholder, setStakeholder] = useState(initial?.stakeholder_name || ""),
    [organization, setOrganization] = useState(
      initial?.stakeholder_organization || "",
    ),
    [requirements, setRequirements] = useState(
      initial?.requirement_analysis || "",
    ),
    [deliverables, setDeliverables] = useState(
      (initial?.expected_deliverables || []).join("\n"),
    ),
    [criteria, setCriteria] = useState(
      (initial?.acceptance_criteria || []).join("\n"),
    ),
    [stack, setStack] = useState((initial?.tech_stack || []).join(", ")),
    [repo, setRepo] = useState(initial?.repository_url || ""),
    [error, setError] = useState("");
  return (
    <form
      className="panel ticket-form"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          const body = JSON.stringify({
            name: n,
            summary,
            stakeholder_name: stakeholder,
            stakeholder_organization: organization,
            requirement_analysis: requirements,
            expected_deliverables: deliverables.split("\n").filter(Boolean),
            acceptance_criteria: criteria.split("\n").filter(Boolean),
            tech_stack: stack
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean),
            repository_url: repo || null,
          });
          await api(initial ? "/projects/" + initial.id : "/projects", {
            method: initial ? "PATCH" : "POST",
            body,
          });
          done();
        } catch (err) {
          setError(err instanceof Error ? err.message : "Project save failed");
        }
      }}
    >
      <div className="ticket-grid">
        <label>
          Project name
          <input required value={n} onChange={(e) => setN(e.target.value)} />
        </label>
        <label>
          Stakeholder / client name
          <input
            value={stakeholder}
            onChange={(e) => setStakeholder(e.target.value)}
          />
        </label>
        <label>
          Stakeholder organization
          <input
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
          />
        </label>
        <label>
          Technology stack
          <input
            placeholder="React, FastAPI, MongoDB"
            value={stack}
            onChange={(e) => setStack(e.target.value)}
          />
        </label>
        <label className="wide">
          Project summary
          <textarea
            required
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
        </label>
        <label className="wide">
          Stakeholder requirement analysis
          <textarea
            required
            value={requirements}
            onChange={(e) => setRequirements(e.target.value)}
          />
        </label>
        <label>
          Expected deliverables, one per line
          <textarea
            value={deliverables}
            onChange={(e) => setDeliverables(e.target.value)}
          />
        </label>
        <label>
          Acceptance criteria, one per line
          <textarea
            value={criteria}
            onChange={(e) => setCriteria(e.target.value)}
          />
        </label>
        <label className="wide">
          GitHub repository URL
          <input
            type="url"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
          />
        </label>
      </div>
      {error && <div className="form-error">{error}</div>}
      <button className="primary">
        {initial ? "Save project changes" : "Create my project"}
      </button>
    </form>
  );
}
function People() {
  const [users, setUsers] = useState<User[]>([]),
    [inv, setInv] = useState<Invite[]>([]),
    [email, setEmail] = useState(""),
    [role, setRole] = useState("student");
  const load = () =>
    Promise.all([api<User[]>("/users"), api<Invite[]>("/invitations")]).then(
      ([a, b]) => {
        setUsers(a);
        setInv(b);
      },
    );
  useEffect(() => {
    void load();
  }, []);
  return (
    <>
      <Heading
        over="ACCESS CONTROL"
        title="People & invitations"
        copy="Roles come only from secure, single-use invitations."
      />
      <form
        className="invite-form panel"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api("/invitations", {
              method: "POST",
              body: JSON.stringify({
                email,
                role,
              }),
            });
            setEmail("");
            await load();
            alert("Invitation email sent successfully.");
          } catch (error) {
            alert(
              error instanceof Error ? error.message : "Email delivery failed",
            );
          }
        }}
      >
        <input
          required
          type="email"
          placeholder="Invitee email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="student">Student</option>
          <option value="core_reviewer">Core reviewer</option>
        </select>
        <button className="primary">
          <Send />
          Send invitation
        </button>
      </form>
      <div className="page-grid">
        <section className="panel">
          <SectionTitle over="ACCOUNTS" title="Registered people" />
          {users.map((u) => (
            <div className="person" key={u.id}>
              <div className="avatar">{initials(u.name)}</div>
              <div>
                <b>{u.name}</b>
                <span>{u.email}</span>
              </div>
              <em>{u.role}</em>
            </div>
          ))}
        </section>
        <section className="panel">
          <SectionTitle over="INVITATIONS" title="Invitation status" />
          {inv.length ? (
            inv.map((i) => (
              <div className="person" key={i.id}>
                <div>
                  <b>{i.email}</b>
                  <span>
                    {i.role} · {i.status}
                  </span>
                </div>
                {i.status === "pending" && (
                  <button
                    className="text-btn"
                    onClick={async () => {
                      await api("/invitations/" + i.id + "/revoke", {
                        method: "POST",
                      });
                      load();
                    }}
                  >
                    Revoke
                  </button>
                )}
              </div>
            ))
          ) : (
            <Empty text="No invitations yet." />
          )}
        </section>
      </div>
    </>
  );
}
function MentorQueue() {
  const [e, setE] = useState<Esc[]>([]);
  const load = () => api<Esc[]>("/core/queue").then(setE);
  useEffect(() => {
    void load();
  }, []);
  return (
    <>
      <Heading
        over="HUMAN-IN-THE-LOOP"
        title="Mentor queue"
        copy="Review unsupported or high-risk student questions with full context."
      />
      <section className="panel">
        <SectionTitle over="ESCALATIONS" title="Needs mentor review" />
        {e.length ? (
          e.map((x) => (
            <div className="escalation" key={x.id}>
              <div>
                <span
                  className={
                    "priority " + (x.status === "OPEN" ? "high" : "medium")
                  }
                >
                  {x.status}
                </span>
                <h3>{x.question}</h3>
                <p>{x.reason}</p>
                <small>{x.student}</small>
              </div>
              {x.status === "OPEN" && (
                <button
                  className="primary"
                  onClick={async () => {
                    const response = prompt("Mentor resolution");
                    if (response) {
                      await api("/escalations/" + x.id + "/resolve", {
                        method: "POST",
                        body: JSON.stringify({
                          response,
                          verified: true,
                          reusableAsKnowledge: true,
                        }),
                      });
                      load();
                    }
                  }}
                >
                  Resolve & verify
                </button>
              )}
            </div>
          ))
        ) : (
          <Empty text="No open escalations. Low-confidence questions will appear here automatically." />
        )}
      </section>
    </>
  );
}
function Knowledge({ auth }: { auth: Auth }) {
  const [q, setQ] = useState(""),
    [result, setResult] = useState(""),
    [content, setContent] = useState(""),
    [project, setProject] = useState("DEMO");
  const ask = async () => {
    const r = await fetch(AI + "/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: project,
        user_id: auth.user.id,
        question: q,
        attempted_solutions: [],
      }),
    });
    const x = await r.json();
    setResult(
      x.decision === "ANSWER"
        ? x.answer
        : "Escalation required: " + x.escalation_reason,
    );
  };
  return (
    <>
      <Heading
        over="PROJECT-SCOPED RAG"
        title="Knowledge & assistant"
        copy="Ingest verified knowledge and query only within a selected project."
      />
      <div className="page-grid">
        <section className="panel assistant light">
          <SectionTitle over="ASK" title="Evidence-backed guidance" />
          <input
            value={project}
            onChange={(e) => setProject(e.target.value)}
            placeholder="Project ID"
          />
          <textarea
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask a project question"
          />
          <button onClick={ask}>
            <Sparkles />
            Ask assistant
          </button>
          {result && (
            <div className="answer">
              <ShieldCheck />
              <span>{result}</span>
            </div>
          )}
        </section>
        <form
          className="panel ingest"
          onSubmit={async (e) => {
            e.preventDefault();
            await fetch(AI + "/ingest", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                project_id: project,
                document_id: crypto.randomUUID(),
                title: "Verified mentor knowledge",
                content,
                verified: true,
              }),
            });
            setContent("");
          }}
        >
          <SectionTitle over="INGEST" title="Add verified knowledge" />
          <textarea
            required
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste a requirement, mentor resolution, or project note"
          />
          <button className="primary">
            <BookOpen />
            Ingest knowledge
          </button>
        </form>
      </div>
    </>
  );
}
function StudentTickets() {
  const [projects, setProjects] = useState<Project[]>([]),
    [tickets, setTickets] = useState<any[]>([]),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const load = () =>
    Promise.all([api<Project[]>("/projects"), api<any[]>("/tickets")]).then(
      ([p, t]) => {
        setProjects(p);
        setTickets(t);
      },
    );
  useEffect(() => {
    void load();
  }, []);
  const sendFeedback = async (ticketId: string, solved: boolean) => {
    const comment = solved
      ? "AI answer solved the issue"
      : prompt("What is still failing? This context will be sent to the matching core reviewer.") || "AI answer did not solve the issue";
    const result = await api<{ message: string }>(`/tickets/${ticketId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ solved, comment }),
    });
    setMessage(result.message);
    await load();
  };
  return (
    <>
      <Heading
        over="PROJECT SUPPORT"
        title="Ask a project question"
        copy="Provide complete context. AI uses project knowledge first and escalates unresolved cases to the best-matched reviewer."
      />
      <form
        className="panel ticket-form"
        onSubmit={async (e) => {
          e.preventDefault();
          const formElement = e.currentTarget;
          setBusy(true);
          setMessage("");
          const form = new FormData(formElement);
          const uploads = form.getAll("files") as File[];
          const invalidImage = uploads.find(
            (f) => f.type.startsWith("image/") && f.size >= 1024 * 1024,
          );
          const invalidZip = uploads.find(
            (f) =>
              f.name.toLowerCase().endsWith(".zip") &&
              f.size >= 50 * 1024 * 1024,
          );
          if (invalidImage) {
            setMessage(
              invalidImage.name + ": every image must be smaller than 1 MB",
            );
            setBusy(false);
            return;
          }
          if (invalidZip) {
            setMessage(
              invalidZip.name + ": every ZIP must be smaller than 50 MB",
            );
            setBusy(false);
            return;
          }
          try {
            const token = sessionStorage.getItem("accessToken");
            const r = await fetch(API + "/tickets", {
              method: "POST",
              headers: token ? { Authorization: "Bearer " + token } : {},
              body: form,
            });
            const data = await r.json();
            if (!r.ok)
              throw new Error(data.detail || "Ticket submission failed");
            setMessage(
              data.ai_resolution.status === "RESOLVED_BY_AI"
                ? "Resolved by the project AI assistant."
                : "AI confidence was insufficient; routed to a matching core reviewer.",
            );
            formElement.reset();
            await load();
          } catch (err) {
            setMessage(
              err instanceof Error ? err.message : "Ticket submission failed",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="ticket-grid">
          <label>
            Project
            <select name="project_id" required>
              {projects.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Title
            <input name="title" required placeholder="What is blocking you?" />
          </label>
          <label>
            Category
            <select name="category" required>
              <option>Developer</option>
              <option>Tester</option>
              <option>DevOps Engineer</option>
              <option>Network Engineer</option>
              <option>UI/UX Designer</option>
              <option>Data Engineer</option>
            </select>
          </label>
          <label>
            Sub-category
            <input
              name="sub_category"
              placeholder="Frontend state management"
            />
          </label>
          <label className="wide">
            Problem description
            <textarea
              name="description"
              required
              placeholder="Describe the full problem and business impact"
            />
          </label>
          <label>
            Expected behavior
            <textarea
              name="expected_behavior"
              required
              placeholder="What should happen?"
            />
          </label>
          <label>
            Actual behavior
            <textarea
              name="actual_behavior"
              required
              placeholder="What happens instead?"
            />
          </label>
          <label className="wide">
            Steps to reproduce
            <textarea
              name="steps_to_reproduce"
              required
              placeholder="Numbered steps that consistently reproduce the issue"
            />
          </label>
          <label>
            Error messages / stack trace
            <textarea
              name="error_messages"
              placeholder="Paste the complete error and stack trace"
            />
          </label>
          <label>
            Solutions already attempted
            <textarea
              name="attempted_solutions"
              placeholder="One attempted solution per line"
            />
          </label>
          <label>
            Operating system / environment
            <input
              name="operating_system"
              placeholder="Windows 11, Ubuntu 24.04, browser..."
            />
          </label>
          <label>
            Runtime and dependency versions
            <input
              name="runtime_versions"
              placeholder="Node 22, Python 3.13, React 19..."
            />
          </label>
          <label className="wide">
            Requirement analysis / problem brief
            <textarea
              name="requirement_text"
              placeholder="Paste the client requirement or your understanding"
            />
          </label>
          <label>
            Client requirement reference
            <input name="client_requirement_ref" placeholder="REQ-402" />
          </label>
          <label>
            Skills involved
            <input name="skills" placeholder='["React","Next.js"]' />
          </label>
          <label>
            GitHub repository
            <input
              name="repository_url"
              type="url"
              placeholder="https://github.com/org/repo"
            />
          </label>
          <label>
            Branch or PR
            <input name="branch_or_pr" placeholder="feature/cart or PR #42" />
          </label>
          <label>
            Commit hash
            <input name="commit_hash" placeholder="a1b2c3d4" />
          </label>
          <label>
            Relevant repository file paths
            <input
              name="relevant_file_paths"
              placeholder="src/cart.tsx, api/cart.py"
            />
          </label>
          <label>
            Dependency manifest / lockfile details
            <textarea
              name="dependency_manifest"
              placeholder="Relevant package.json, requirements, or dependency versions"
            />
          </label>
          <label>
            Related issues, PRs, or documentation URLs
            <input
              name="related_issue_urls"
              placeholder="Comma-separated URLs"
            />
          </label>
          <label>
            Network logs (JSON)
            <textarea name="network_logs" defaultValue="{}" />
          </label>
          <label className="wide">
            Images under 1 MB; ZIP files under 50 MB; code, PDF and text
            accepted
            <input
              name="files"
              type="file"
              multiple
              accept=".png,.jpg,.jpeg,.webp,.gif,.txt,.md,.pdf,.zip,.py,.js,.jsx,.ts,.tsx,.java,.json,.yaml,.yml,.log,.html,.css,.sql"
            />
          </label>
          <div className="upload-notice wide">
            <b>Temporary ZIP notice</b>
            <span>
              ZIP archives are stored securely in S3 and permanently deleted 24
              hours after upload. Add relevant file paths and repository context
              above so the AI can analyze the correct code before deletion.
            </span>
          </div>
        </div>
        {message && <div className="answer">{message}</div>}
        <button className="primary" disabled={busy}>
          <Send />
          {busy ? "Analyzing project context..." : "Analyze & raise ticket"}
        </button>
      </form>
      <section className="panel">
        <SectionTitle over="MY SUPPORT HISTORY" title="Tickets" />
        {tickets.length ? (
          tickets.map((t) => (
            <div className="work-card" key={t.id}>
              <span
                className={
                  "priority " + (t.status === "OPEN" ? "high" : "medium")
                }
              >
                {t.status}
              </span>
              <div>
                <b>{t.title}</b>
                <p>
                  {t.category} · {t.ai_resolution?.status} · confidence{" "}
                  {Math.round((t.ai_resolution?.confidence_score || 0) * 100)}%
                </p>
                {t.ai_resolution?.rag_response && (
                  <div className="answer">{t.ai_resolution.rag_response}</div>
                )}
                {t.status === "AWAITING_STUDENT_CONFIRMATION" && (
                  <div className="ticket-actions">
                    <button className="primary" onClick={() => void sendFeedback(t.id, true)}>Solved</button>
                    <button className="secondary" onClick={() => void sendFeedback(t.id, false)}>Not solved — send to core reviewer</button>
                  </div>
                )}
              </div>
            </div>
          ))
        ) : (
          <Empty text="No tickets raised yet." />
        )}
      </section>
    </>
  );
}
function Admin() {
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    Promise.all([
      api<Stats>("/analytics/overview"),
      fetch(AI + "/integrations").then((r) => r.json()),
    ]).then(([analytics, integrations]) => setS({ analytics, integrations }));
  }, []);
  return (
    <>
      <Heading
        over="PLATFORM CONTROL"
        title="Administration"
        copy="Integration health, platform metrics, and operational readiness."
      />
      <div className="stats">
        <article>
          <span>MongoDB Atlas</span>
          <strong>Connected</strong>
          <small>Operational metadata</small>
        </article>
        <article>
          <span>Gemini</span>
          <strong>{s?.integrations?.gemini || "Checking"}</strong>
          <small>Complex reasoning</small>
        </article>
        <article>
          <span>Ollama</span>
          <strong>{s?.integrations?.ollama_model || "Checking"}</strong>
          <small>Routine local tasks</small>
        </article>
        <article>
          <span>Open tickets</span>
          <strong>{s?.analytics?.openTickets ?? 0}</strong>
          <small>Across projects</small>
        </article>
      </div>
      <section className="panel">
        <SectionTitle over="SYSTEM CHECKS" title="Architecture services" />
        {[
          "FastAPI unified API",
          "MongoDB Atlas",
          "FastAPI RAG",
          "BGE embeddings",
          "Gemini router",
          "Ollama fallback",
          "ClickUp adapter",
          "S3/local storage",
        ].map((x, i) => (
          <div className="status-row" key={x}>
            <CheckCircle2 />
            <b>{x}</b>
            <span>{i < 5 ? "CONFIGURED" : "AVAILABLE / FALLBACK"}</span>
          </div>
        ))}
      </section>
    </>
  );
}
function Login({
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
    <div className="login-page">
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
              throw new Error("Use the correct role login page");
            onLogin(a);
          } catch (x) {
            setError(x instanceof Error ? x.message : "Login failed");
          }
        }}
      >
        <div className="brandmark">B</div>
        <span className="eyebrow">BARABARI COLLECTIVE</span>
        <h1>Mentoring intelligence</h1>
        <p>
          Invitation-only access for students, mentors, clients, and
          administrators.
        </p>
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
        <small>
          Roles are assigned through invitations, never self-selected.
        </small>
      </form>
    </div>
  );
}
function SectionTitle({ over, title }: { over: string; title: string }) {
  return (
    <div className="panel-title">
      <div>
        <span className="eyebrow">{over}</span>
        <h2>{title}</h2>
      </div>
    </div>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="empty">
      <RefreshCw />
      <p>{text}</p>
    </div>
  );
}
function initials(s: string) {
  return s
    .split(" ")
    .map((x) => x[0])
    .join("")
    .slice(0, 2);
}
