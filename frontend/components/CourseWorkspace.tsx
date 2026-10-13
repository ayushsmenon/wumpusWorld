import {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react"
import { Link } from "react-router-dom"

type IconName = "plus" | "search" | "folder" | "pdf" | "slides" | "notes" | "more" | "chevron" | "spark" | "paperclip" | "arrow" | "panel" | "focus" | "close" | "check" | "clock" | "book" | "warning" | "minus" | "settings" | "reset" | "download"

const iconPaths: Record<IconName, ReactNode> = {
  plus: <path d="M12 5v14M5 12h14" />,
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </>
  ),
  folder: <path d="M3.5 7.5h6l2-2h9v13h-17z" />,
  pdf: (
    <>
      <path d="M6 3.5h8l4 4v13H6z" />
      <path d="M14 3.5v4h4M9 13h6M9 16h4" />
    </>
  ),
  slides: (
    <>
      <rect x="4" y="4" width="16" height="13" rx="1" />
      <path d="M8 20h8M12 17v3M8 8h8M8 11h5" />
    </>
  ),
  notes: (
    <>
      <path d="M6 3.5h12v17H6z" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </>
  ),
  more: (
    <>
      <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  chevron: <path d="m9 7 5 5-5 5" />,
  spark: (
    <>
      <path d="M12 3.5 13.6 9l4.9 1.5-4.9 1.6L12 17.5l-1.6-5.4-4.9-1.6L10.4 9z" />
      <path d="m18 16 .6 2.1 1.9.6-1.9.6L18 21l-.6-1.7-1.9-.6 1.9-.6z" />
    </>
  ),
  paperclip: (
    <path d="m8.5 12.5 5.8-5.8a3 3 0 0 1 4.2 4.2l-7.7 7.7a5 5 0 0 1-7.1-7.1l7.5-7.5" />
  ),
  arrow: (
    <>
      <path d="M5 12h14M14 7l5 5-5 5" />
    </>
  ),
  panel: (
    <>
      <rect x="3.5" y="4" width="17" height="16" rx="1.5" />
      <path d="M14 4v16" />
    </>
  ),
  focus: (
    <>
      <path d="M8 4H4v4M16 4h4v4M20 16v4h-4M4 16v4h4" />
      <circle cx="12" cy="12" r="2.5" />
    </>
  ),
  close: <path d="m6 6 12 12M18 6 6 18" />,
  check: <path d="m5 12 4 4L19 6" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7v5l3.5 2" />
    </>
  ),
  book: (
    <>
      <path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H12v17H7.5A3.5 3.5 0 0 0 4 22z" />
      <path d="M20 5.5A3.5 3.5 0 0 0 16.5 2H12v17h4.5A3.5 3.5 0 0 1 20 22z" />
    </>
  ),
  warning: (
    <>
      <path d="M12 3.5 21 20H3z" />
      <path d="M12 9v5M12 17.5v.1" />
    </>
  ),
  minus: <path d="M5 12h14" />,
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19 13.5v-3l-2-.7-.8-1.8.9-1.9L15 4l-1.9.9-1.9-.8-.7-2h-3l-.7 2-1.8.8L3.1 4 1 6.1 1.9 8 1 9.8v3l2 .7.8 1.8-.9 1.9L5 19.3l1.9-.9 1.9.8.7 2h3l.7-2 1.8-.8 1.9.9 2.1-2.1-.9-1.9z" />
    </>
  ),
  reset: (
    <>
      <path d="M4.5 9A8 8 0 1 1 5 16" />
      <path d="M4.5 4v5h5" />
    </>
  ),
  download: (
    <>
      <path d="M12 3v12M7 10l5 5 5-5" />
      <path d="M5 20h14" />
    </>
  ),
}

function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      className="icon"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
    >
      {iconPaths[name]}
    </svg>
  )
}

const files: { name: string; meta: string; type: IconName }[] = []

const graphNodes: { id: string; x: number; y: number; kind: string; r: number }[] = []

const graphEdges: string[][] = []

function FileRow({
  file,
  active,
  onClick,
}: {
  file: typeof files[number]
  active: boolean
  onClick: () => void
}) {
  return (
    <button className={`file-row ${active ? "active" : ""}`} onClick={onClick}>
      <span className="file-type">
        {file.type === "slides"
          ? "SLIDES"
          : file.type === "notes"
            ? "NOTE"
            : "PDF"}
      </span>
      <span className="file-copy">
        <span className="file-name">{file.name}</span>
        <span className="file-meta">{file.meta}</span>
      </span>
      {active && <span className="active-mark" />}
    </button>
  )
}

function Citation({
  children,
  active,
  onClick,
}: {
  children: ReactNode
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      className={`citation ${active ? "selected" : ""}`}
      onClick={onClick}
    >
      [{children}]
    </button>
  )
}

function KnowledgeGraph({
  selected,
  onSelect,
  query = "",
  zoom = 1,
}: {
  selected: string
  onSelect: (id: string) => void
  query?: string
  zoom?: number
}) {
  const byId = Object.fromEntries(graphNodes.map((node) => [node.id, node]))
  return (
    <svg
      aria-label="Interactive concept map"
      className="graph"
      role="img"
      style={{ transform: `scale(${zoom})` }}
      viewBox="0 0 350 245"
    >
      <g className="edges">
        {graphEdges.map(([from, to]) => (
          <line
            key={`${from}-${to}`}
            x1={byId[from].x}
            x2={byId[to].x}
            y1={byId[from].y}
            y2={byId[to].y}
          />
        ))}
      </g>
      {graphNodes.map((node) => {
        const isSelected = selected === node.id
        return (
          <g
            className={`node ${node.kind} ${isSelected ? "selected" : ""} ${
              query && !node.id.toLowerCase().includes(query.toLowerCase())
                ? "filtered"
                : ""
            }`}
            key={node.id}
            onClick={() => onSelect(node.id)}
            role="button"
            tabIndex={0}
          >
            {isSelected && (
              <circle
                className="node-ring"
                cx={node.x}
                cy={node.y}
                r={node.r + 7}
              />
            )}
            <circle cx={node.x} cy={node.y} r={node.r} />
            <text
              className={node.x > 250 ? "label-end" : ""}
              x={node.x > 250 ? node.x - 10 : node.x + 10}
              y={node.y + 3}
            >
              {node.id}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function CourseWorkspace({
  course,
  onUpload,
}: {
  course?: { subject?: string; title: string; description?: string; materials?: { filename: string; file_type: string; status: string; unit_count: number }[] }
  onUpload?: (file: File) => Promise<unknown>
}) {
  const [activeFile, setActiveFile] = useState("")
  const [query, setQuery] = useState("")
  const [message, setMessage] = useState("")
  const [selectedCitation, setSelectedCitation] = useState("slides")
  const [selectedConcept, setSelectedConcept] = useState("")
  const [conversationStarted, setConversationStarted] = useState(false)
  const [responseStatus, setResponseStatus] =
    useState<"idle" | "generating" | "error">("idle")
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState("")
  const [sentMessage, setSentMessage] = useState("")
  const [leftPanelOpen, setLeftPanelOpen] = useState(true)
  const [rightPanelOpen, setRightPanelOpen] = useState(true)
  const [masteryOpen, setMasteryOpen] = useState(true)
  const [graphFullscreen, setGraphFullscreen] = useState(false)
  const [graphZoom, setGraphZoom] = useState(1)
  const [graphQuery, setGraphQuery] = useState("")
  const [graphView, setGraphView] = useState<"graph" | "outline">("graph")
  const [leftWidth, setLeftWidth] = useState(18)
  const [rightWidth, setRightWidth] = useState(30)
  const [masteryHeight, setMasteryHeight] = useState(42)

  const visibleFiles = (course?.materials || []).map((material) => ({
    name: material.filename,
    meta: material.status === "parsed" ? `${material.unit_count} pages or slides` : material.status,
    type: material.file_type === "pptx" ? "slides" as IconName : "pdf" as IconName,
  }))
  const filteredFiles = useMemo(
    () =>
      visibleFiles.filter((file) =>
        file.name.toLowerCase().includes(query.toLowerCase()),
      ),
    [query],
  )

  function submitMessage(event: FormEvent) {
    event.preventDefault()
    const trimmed = message.trim()
    if (!trimmed) return
    setSentMessage(trimmed)
    setMessage("")
    setConversationStarted(false)
    setResponseStatus("error")
    setMasteryOpen(true)
    window.setTimeout(() => setMasteryOpen(false), 4200)
  }

  async function addMaterials(file?: File) {
    if (!file || !onUpload) return
    setUploading(true)
    setUploadError("")
    try {
      await onUpload(file)
      window.location.reload()
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed")
      setUploading(false)
    }
  }

  useEffect(() => {
    function handleKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape") setGraphFullscreen(false)
      if ((event.metaKey || event.ctrlKey) && event.key === "\\") {
        event.preventDefault()
        setLeftPanelOpen((open) => !open)
      }
    }
    window.addEventListener("keydown", handleKeyboard)
    return () => window.removeEventListener("keydown", handleKeyboard)
  }, [])

  useEffect(() => {
    if (window.matchMedia("(max-width: 1024px)").matches) {
      setLeftPanelOpen(false)
      setRightPanelOpen(false)
    }
  }, [])

  function retryResponse() {
    setResponseStatus("generating")
    window.setTimeout(() => setResponseStatus("idle"), 1800)
  }

  function beginResize(event: ReactPointerEvent<HTMLButtonElement>) {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = rightWidth

    function resize(moveEvent: PointerEvent) {
      const delta = ((startX - moveEvent.clientX) / window.innerWidth) * 100
      setRightWidth(Math.min(60, Math.max(25, startWidth + delta)))
    }

    function stopResize() {
      window.removeEventListener("pointermove", resize)
      window.removeEventListener("pointerup", stopResize)
    }

    window.addEventListener("pointermove", resize)
    window.addEventListener("pointerup", stopResize)
  }

  function beginLeftResize(event: ReactPointerEvent<HTMLButtonElement>) {
    event.preventDefault()

    function resize(moveEvent: PointerEvent) {
      const width = (moveEvent.clientX / window.innerWidth) * 100
      setLeftWidth(Math.min(35, Math.max(12, width)))
    }

    function stopResize() {
      window.removeEventListener("pointermove", resize)
      window.removeEventListener("pointerup", stopResize)
    }

    window.addEventListener("pointermove", resize)
    window.addEventListener("pointerup", stopResize)
  }

  function beginVerticalResize(event: ReactPointerEvent<HTMLButtonElement>) {
    event.preventDefault()

    function resize(moveEvent: PointerEvent) {
      const height = 100 - (moveEvent.clientY / window.innerHeight) * 100
      setMasteryHeight(Math.min(65, Math.max(25, height)))
    }

    function stopResize() {
      window.removeEventListener("pointermove", resize)
      window.removeEventListener("pointerup", stopResize)
    }

    window.addEventListener("pointermove", resize)
    window.addEventListener("pointerup", stopResize)
  }

  function exportGraph() {
    setUploadError("Graph export is unavailable until concepts are generated.")
  }

  const relatedConcepts: Record<string, string[]> = {}

  return (
    <main
      className={`app-shell ${leftPanelOpen ? "" : "left-collapsed"} ${
        rightPanelOpen ? "" : "insights-collapsed"
      }`}
      style={
        {
          "--left-width": leftPanelOpen ? `${leftWidth}%` : "48px",
          "--right-width": rightPanelOpen ? `${rightWidth}%` : "48px",
          "--mastery-height": `${masteryHeight}%`,
        } as CSSProperties
      }
    >
      <aside className="library-panel">
        <button
          aria-label="Resize materials panel"
          className="resize-handle resize-left"
          onPointerDown={beginLeftResize}
          title="Drag to resize"
        />
        <div className="collapsed-rail">
          <button
            aria-label="Open materials"
            onClick={() => setLeftPanelOpen(true)}
            title="Materials · ⌘ + \\"
          >
            <Icon name="folder" size={18} />
          </button>
          <button aria-label="Open materials to add a file" onClick={() => setLeftPanelOpen(true)}>
            <Icon name="plus" size={18} />
          </button>
          <span title={`${course?.subject || "Course"} · ${course?.title}`}>
            {(course?.subject || course?.title || "Course").slice(0, 2).toUpperCase()}
          </span>
        </div>
        <div className="brand-row">
          <Link aria-label="Return to Wumpus World home" className="wordmark" to="/">
            Wumpus World
          </Link>
          <button aria-label="Workspace options" className="icon-button quiet">
            <Icon name="more" />
          </button>
          <button
            aria-label="Collapse materials"
            className="icon-button quiet collapse-library"
            onClick={() => setLeftPanelOpen(false)}
            title="Collapse · ⌘ + \\"
          >
            <Icon name="chevron" size={15} />
          </button>
        </div>

        <button className="course-selector">
          <span>
            <small>ACTIVE COURSE</small>
            <strong>
              {course?.subject || "Course"} · {course?.title}
            </strong>
          </span>
          <Icon name="chevron" size={14} />
        </button>

        <label className="add-materials">
          <Icon name="plus" size={15} />
          <span>Add materials</span>
          <input accept=".pdf,.pptx" hidden onChange={(event) => addMaterials(event.target.files?.[0])} type="file" />
        </label>

        <label className="search-box">
          <Icon name="search" size={15} />
          <input
            aria-label="Search materials"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="⌘K  Search materials"
            value={query}
          />
        </label>

        <div className="library-scroll">
          <div className="section-heading">
            <span>Modules</span>
            <button aria-label="Add folder" className="icon-button quiet">
              <Icon name="plus" size={13} />
            </button>
          </div>

          <div className="module-group">
            <button className="module-title">
              <span>01</span>
              <strong>Foundations</strong>
              <Icon name="chevron" size={14} />
            </button>
          </div>

          <div className="module-group active-module">
            <button className="module-title">
              <span>02</span>
              <strong>Graph traversal</strong>
              <Icon name="chevron" size={14} />
            </button>
            <div className="files-list">
              {uploading && (
                <div className="processing-row">
                  <span className="processing-icon">
                    <span />
                  </span>
                  <span className="file-copy">
                    <span className="file-name">Uploading material</span>
                    <span className="processing-label">Processing with ingestion</span>
                  </span>
                </div>
              )}
              {filteredFiles.map((file) => (
                <FileRow
                  active={file.name === activeFile}
                  file={file}
                  key={file.name}
                  onClick={() =>
                    setActiveFile(activeFile === file.name ? "" : file.name)
                  }
                />
              ))}
              {!filteredFiles.length && (
                <div className="empty-search">No materials match “{query}”</div>
              )}
            </div>
          </div>

          <div className="module-group">
            <button className="module-title">
              <span>03</span>
              <strong>Shortest paths</strong>
              <Icon name="chevron" size={14} />
            </button>
          </div>
        </div>
      </aside>

      <section className="learning-panel">
        <header className="learning-header">
          <div className="breadcrumb">
            <span>{course?.subject || "Course"}</span>
            <i>/</i>
            <span>Module 02</span>
            <i>/</i>
            <strong>Graph Traversal</strong>
          </div>
          <div className="header-actions">
            <button
              aria-label="Open course materials"
              className="icon-button mobile-panel-button"
              onClick={() => setLeftPanelOpen(true)}
            >
              <Icon name="folder" />
            </button>
            <button
              aria-label="Start a new conversation"
              className="icon-button"
              onClick={() => {
                setConversationStarted(false)
                setSentMessage("")
                setResponseStatus("idle")
              }}
              title="New conversation"
            >
              <Icon name="plus" />
            </button>
            <button
              aria-label="Toggle insights panel"
              className="icon-button"
              onClick={() => setRightPanelOpen((value) => !value)}
            >
              <Icon name="panel" />
            </button>
          </div>
        </header>

        <div className="conversation">
          {uploading && (
            <div className="conversation-status processing-state" role="status">
              <span className="processing-icon">
                <span />
              </span>
              <div>
                <strong>Preparing uploaded material</strong>
                <span>You can keep studying while concepts are extracted.</span>
              </div>
            </div>
          )}
          {!activeFile && (
            <div className="conversation-status material-state" role="status">
              <Icon name="book" size={16} />
              <div>
                <strong>No material selected</strong>
                <span>
                  Select a source to ground answers in your course content.
                </span>
              </div>
            </div>
          )}

          {!conversationStarted ? (
            <div className="conversation-empty">
              <span className="empty-kicker">MODULE 02 · GRAPH TRAVERSAL</span>
              <h2>What would you like to understand?</h2>
              <p>
                Ask about a concept, compare approaches, or test your recall
                using the selected course materials.
              </p>
              <div>
                {[
                  "Explain breadth-first search",
                  "Compare BFS and DFS",
                  "Quiz me on graph traversal",
                ].map((prompt) => (
                  <button key={prompt} onClick={() => setMessage(prompt)}>
                    {prompt}
                    <Icon name="arrow" size={13} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              <div className="date-divider">
                <span>Today</span>
              </div>

              <div className="user-message">
                <div className="speaker">You</div>
                <p>
                  What’s the difference between breadth-first and depth-first
                  search? When should I use each?
                </p>
              </div>

              <article className="tutor-response">
                <div className="response-content">
                  <p className="lead">
                    Both algorithms explore a graph, but the order in which they
                    visit nodes gives them different strengths.
                  </p>

                  <h2>Breadth-first search explores by distance</h2>
                  <p>
                    BFS visits every neighbor of the current node before moving
                    to the next level. It uses a<strong> queue</strong>, so the
                    earliest discovered node is explored first.
                  </p>
                  <div className="algorithm-line">
                    <code>
                      enqueue(start) → visit neighbors → enqueue unvisited →
                      repeat
                    </code>
                  </div>
                  <p>
                    This makes BFS the right choice when you need the shortest
                    path in an unweighted graph, or when the answer is likely to
                    be close to the starting point.
                    <Citation
                      active={selectedCitation === "slides"}
                      onClick={() => setSelectedCitation("slides")}
                    >
                      Selected source
                    </Citation>
                  </p>

                  <h2>Depth-first search follows one path deeply</h2>
                  <p>
                    DFS explores as far as possible along a branch before
                    backtracking. It uses a<strong> stack</strong>—either
                    explicitly or through recursion.
                  </p>

                  <div className="comparison">
                    <div className="comparison-row comparison-head">
                      <span>Consideration</span>
                      <span>BFS</span>
                      <span>DFS</span>
                    </div>
                    <div className="comparison-row">
                      <span>Data structure</span>
                      <span>Queue</span>
                      <span>Stack</span>
                    </div>
                    <div className="comparison-row">
                      <span>Shortest path</span>
                      <span>
                        <Icon name="check" size={13} /> Guaranteed*
                      </span>
                      <span>Not guaranteed</span>
                    </div>
                    <div className="comparison-row">
                      <span>Memory</span>
                      <span>Higher on wide graphs</span>
                      <span>Lower in many cases</span>
                    </div>
                  </div>

                  <p>
                    Choose DFS for cycle detection, topological sorting, and
                    exhaustive path exploration.
                    <Citation
                      active={selectedCitation === "book"}
                      onClick={() => setSelectedCitation("book")}
                    >
                      Selected source
                    </Citation>
                  </p>
                  <p className="footnote">
                    * For unweighted graphs. Both run in O(V + E) with an
                    adjacency-list representation.
                  </p>
                </div>
              </article>

              {sentMessage && (
                <div className="new-message">
                  <div className="user-message">
                    <div className="speaker">You</div>
                    <p>{sentMessage}</p>
                  </div>
                  {responseStatus === "generating" && (
                    <div className="thinking" aria-live="polite">
                      <span className="thinking-dots">
                        <i />
                        <i />
                        <i />
                      </span>
                      Reading across your materials
                    </div>
                  )}
                  {responseStatus === "error" && (
                    <div className="response-error" role="alert">
                      <Icon name="warning" size={15} />
                      <span>
                        <strong>Response interrupted</strong>
                        Your materials are still available.
                      </span>
                      <button onClick={retryResponse}>Retry</button>
                    </div>
                  )}
                </div>
              )}

              <div className="follow-up">
                <span>Keep exploring</span>
                <div>
                  {[
                    "Show me a visual example",
                    "Quiz me on this",
                    "Compare their time complexity",
                  ].map((prompt) => (
                    <button key={prompt} onClick={() => setMessage(prompt)}>
                      {prompt}
                      <Icon name="arrow" size={13} />
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="composer-wrap">
          <form className="composer" onSubmit={submitMessage}>
            <textarea
              aria-label="Ask about your materials"
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              placeholder="Ask a question about this module…"
              rows={1}
              value={message}
            />
            <div className="composer-actions">
              <button
                aria-label="Attach a material"
                className="attach-button"
                type="button"
              >
                <Icon name="paperclip" />
              </button>
              <span>Answers use your selected materials</span>
              <button
                aria-label="Send message"
                className="send-button"
                disabled={!message.trim()}
                type="submit"
              >
                <Icon name="arrow" size={16} />
              </button>
            </div>
          </form>
        </div>
      </section>

      <aside className="insights-panel">
        <div className="right-rail">
          <button
            aria-label="Open concept graph"
            onClick={() => setRightPanelOpen(true)}
            title="Open concept graph"
          >
            <Icon name="focus" size={17} />
            <span>Graph</span>
          </button>
          <button
            aria-label="Open topic mastery"
            onClick={() => {
              setRightPanelOpen(true)
              setMasteryOpen(true)
            }}
            title="Topic mastery is not available yet"
          >
            <span className="rail-metric">68</span>
          </button>
        </div>
        <button
          aria-label="Resize insights panel"
          className="resize-handle"
          onPointerDown={beginResize}
          title="Drag to resize"
        />
        <section className="concept-section">
          <div className="panel-title">
            <div>
              <span className="eyebrow">KNOWLEDGE</span>
              <h2>Concept map</h2>
            </div>
            <div>
              <button aria-label="Graph layout" className="icon-button quiet">
                <Icon name="settings" size={15} />
              </button>
              <button
                aria-label="Open graph fullscreen"
                className="icon-button quiet"
                onClick={() => setGraphFullscreen(true)}
              >
                <Icon name="focus" size={15} />
              </button>
              <button
                aria-label="Close concept panel"
                className="icon-button quiet"
                onClick={() => setRightPanelOpen(false)}
              >
                <Icon name="close" size={15} />
              </button>
            </div>
          </div>

          <div className="graph-wrap">
            <div className="graph-empty">Concepts will appear here after course materials are processed.</div>
            <div className="graph-legend">
              <span>
                <i className="learned" /> Learned
              </span>
              <span>
                <i className="unexplored" /> Unexplored
              </span>
            </div>
            {selectedConcept && (
              <div className="concept-tooltip">
                <span>Selected concept</span>
                <strong>{selectedConcept}</strong>
              </div>
            )}
            <div className="docked-graph-controls">
              <button
                aria-label="Zoom out"
                onClick={() =>
                  setGraphZoom((zoom) => Math.max(0.75, zoom - 0.1))
                }
              >
                <Icon name="minus" size={13} />
              </button>
              <button
                aria-label="Reset graph view"
                onClick={() => setGraphZoom(1)}
              >
                <Icon name="reset" size={12} />
              </button>
              <button
                aria-label="Zoom in"
                onClick={() =>
                  setGraphZoom((zoom) => Math.min(1.4, zoom + 0.1))
                }
              >
                <Icon name="plus" size={13} />
              </button>
            </div>
          </div>

          <div className="concept-focus">
            <span className="concept-dot" />
            <div>
              <small>SELECTED CONCEPT</small>
              <strong>{selectedConcept}</strong>
              <p>
                Related:{" "}
                {(relatedConcepts[selectedConcept] || ["Graph traversal"]).join(
                  " · ",
                )}
              </p>
            </div>
          </div>
        </section>

        <button
          aria-label="Resize graph and mastery panels"
          className="vertical-resize-handle"
          onPointerDown={beginVerticalResize}
          title="Drag to resize"
        />
        <section
          className={`progress-section ${masteryOpen ? "" : "minimized"}`}
        >
          <button
            className="mastery-toggle"
            onClick={() => setMasteryOpen((open) => !open)}
          >
            <div>
              <span className="eyebrow">THIS COURSE</span>
              <h2>Topic mastery</h2>
            </div>
            <span className="mastery-live">Unavailable</span>
            <Icon name="chevron" size={14} />
          </button>

          <div className="mastery-content">
            <div className="mastery-overview">
              <div className="mastery-copy">
                <strong>—</strong>
                <span>Progress will appear after studying</span>
              </div>
              <div className="mastery-bar">
                <span style={{ width: "0%" }} />
              </div>
              <span className="mastery-note">No mastery data yet</span>
            </div>

            <div className="progress-list">
              <div className="empty-search">Mastery will appear after you study this course.</div>
            </div>

            <button className="continue-link">
              <span>Test your understanding</span>
              <Icon name="arrow" size={15} />
            </button>
          </div>
        </section>
      </aside>

      {graphFullscreen && (
        <div
          aria-label="Concept map fullscreen"
          className="graph-overlay"
          role="dialog"
        >
          <div className="fullscreen-graph">
            <header>
              <div>
                <span className="eyebrow">{course?.subject || "Course"}</span>
                <h2>Concept map</h2>
              </div>
              <button
                className="exit-fullscreen"
                onClick={() => setGraphFullscreen(false)}
              >
                <Icon name="close" size={15} />
                Exit fullscreen <kbd>ESC</kbd>
              </button>
            </header>

            <div className="fullscreen-toolbar">
              <label className="graph-search">
                <Icon name="search" size={14} />
                <input
                  aria-label="Search concepts"
                  onChange={(event) => setGraphQuery(event.target.value)}
                  placeholder="Search concepts…"
                  value={graphQuery}
                />
              </label>
              <div className="view-toggle">
                <button
                  className={graphView === "graph" ? "active" : ""}
                  onClick={() => setGraphView("graph")}
                >
                  Force-directed graph
                </button>
                <button
                  className={graphView === "outline" ? "active" : ""}
                  onClick={() => setGraphView("outline")}
                >
                  Outline tree
                </button>
              </div>
              <button className="export-button" disabled onClick={exportGraph}>
                <Icon name="download" size={14} />
                Export Markdown
              </button>
            </div>

            <div className="fullscreen-canvas">
              <div className="outline-tree graph-empty">
                <strong>No concepts yet</strong>
                <small>Process course materials to generate a concept map.</small>
              </div>
              <div className="zoom-controls">
                <button
                  aria-label="Zoom in"
                  onClick={() =>
                    setGraphZoom((zoom) => Math.min(1.8, zoom + 0.1))
                  }
                >
                  <Icon name="plus" size={15} />
                </button>
                <button
                  aria-label="Zoom out"
                  onClick={() =>
                    setGraphZoom((zoom) => Math.max(0.6, zoom - 0.1))
                  }
                >
                  <Icon name="minus" size={15} />
                </button>
                <span>{Math.round(graphZoom * 100)}%</span>
                <button onClick={() => setGraphZoom(1)}>
                  <Icon name="reset" size={14} />
                  Reset view
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
