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
import {
  askTutor,
  generateAssessment,
  getLearnerMastery,
  getRecommendations,
  submitAssessmentAnswer,
} from "../lib/api"

type IconName =
  | "plus"
  | "search"
  | "folder"
  | "pdf"
  | "slides"
  | "notes"
  | "more"
  | "chevron"
  | "spark"
  | "paperclip"
  | "arrow"
  | "panel"
  | "focus"
  | "close"
  | "check"
  | "clock"
  | "book"
  | "warning"
  | "minus"
  | "settings"
  | "reset"
  | "download"

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

interface CitationItem {
  id: number
  source_type: string
  source_uri?: string | null
  filename?: string | null
  page_number?: number | null
  slide_number?: number | null
  video_timestamp?: number | null
  topic_title?: string | null
  location: string
  label: string
  text_snippet?: string | null
}

interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  citations?: CitationItem[]
  is_grounded?: boolean
  out_of_scope?: boolean
}

interface RecommendationTopic {
  topic_id: number
  title: string
  status: string
  mastery_score: number
  confidence: number
  priority: number
  reason: string
  blocking_prerequisites: Array<{ topic_id: number; title: string; mastery_score: number }>
}

interface WeakTopicItem {
  topic_id: number
  title: string
  mastery_score: number
  confidence: number
  deficit: number
  priority: number
  root_cause_prerequisites: Array<{ prerequisite_id: number; title: string; mastery_score: number }>
}

interface AssessmentQuestion {
  id: number
  question_type: "MCQ" | "short_answer" | "numerical"
  difficulty: string
  prompt: string
  options?: string[] | null
  correct_answer: string
  explanation?: string | null
}

interface AssessmentData {
  assessment_id: number
  student_id: number
  topic_id: number
  topic_title: string
  assessment_type: string
  questions: AssessmentQuestion[]
}

function FileRow({
  file,
  active,
  onClick,
}: {
  file: { name: string; meta: string; type: IconName }
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

export default function CourseWorkspace({
  course,
  onUpload,
}: {
  course?: {
    id?: string
    subject?: string
    title: string
    description?: string
    materials?: { filename: string; file_type: string; status: string; unit_count: number }[]
  }
  onUpload?: (file: File) => Promise<unknown>
}) {
  const courseId = course?.id || "1"
  const studentId = 1

  const [activeFile, setActiveFile] = useState("")
  const [query, setQuery] = useState("")
  const [message, setMessage] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [selectedCitationDetail, setSelectedCitationDetail] = useState<CitationItem | null>(null)
  const [selectedConcept, setSelectedConcept] = useState("Graph traversal")
  const [responseStatus, setResponseStatus] = useState<"idle" | "generating" | "error">("idle")
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState("")
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

  const [studyPath, setStudyPath] = useState<RecommendationTopic[]>([])
  const [weakTopics, setWeakTopics] = useState<WeakTopicItem[]>([])
  const [nextTopics, setNextTopics] = useState<RecommendationTopic[]>([])
  const [masteries, setMasteries] = useState<Array<{ topic_id: number; mastery_score: number; confidence: number }>>([])

  const [quizOpen, setQuizOpen] = useState(false)
  const [quizLoading, setQuizLoading] = useState(false)
  const [quizData, setQuizData] = useState<AssessmentData | null>(null)
  const [quizAnswers, setQuizAnswers] = useState<Record<number, string>>({})
  const [quizResults, setQuizResults] = useState<Record<number, { is_correct: boolean; feedback: string; correct_answer: string }>>({})
  const [submittingQ, setSubmittingQ] = useState<Record<number, boolean>>({})

  const visibleFiles = (course?.materials || []).map((material) => ({
    name: material.filename,
    meta: material.status === "parsed" ? `${material.unit_count} pages or slides` : material.status,
    type: material.file_type === "pptx" ? ("slides" as IconName) : ("pdf" as IconName),
  }))

  const filteredFiles = useMemo(
    () =>
      visibleFiles.filter((file) =>
        file.name.toLowerCase().includes(query.toLowerCase()),
      ),
    [visibleFiles, query],
  )

  const averageMastery = useMemo(() => {
    if (!masteries.length) return 0
    const sum = masteries.reduce((acc, m) => acc + m.mastery_score, 0)
    return Math.round((sum / masteries.length) * 100)
  }, [masteries])

  async function loadLearnerInsights() {
    try {
      const recRes = await getRecommendations(studentId, courseId)
      if (recRes) {
        setStudyPath(recRes.study_path || [])
        setWeakTopics(recRes.weak_topics || [])
        setNextTopics(recRes.next_topics || [])
      }
      const masteryRes = await getLearnerMastery(studentId, courseId)
      if (Array.isArray(masteryRes)) {
        setMasteries(masteryRes)
      }
    } catch {
      setStudyPath([])
      setWeakTopics([])
      setNextTopics([])
      setMasteries([])
    }
  }

  useEffect(() => {
    loadLearnerInsights()
  }, [courseId])

  async function handleSendMessage(textToSend?: string) {
    const raw = textToSend !== undefined ? textToSend : message
    const trimmed = raw.trim()
    if (!trimmed) return

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
    }
    setMessages((prev) => [...prev, userMsg])
    setMessage("")
    setResponseStatus("generating")

    try {
      const result = await askTutor(trimmed, courseId)
      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: result.answer,
        citations: result.citations || [],
        is_grounded: result.is_grounded,
        out_of_scope: result.out_of_scope,
      }
      setMessages((prev) => [...prev, assistantMsg])
      if (result.citations && result.citations.length > 0) {
        setSelectedCitationDetail(result.citations[0])
      }
      setResponseStatus("idle")
    } catch (err) {
      setResponseStatus("error")
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: err instanceof Error ? err.message : "Unable to reach grounded tutor service.",
        is_grounded: false,
      }
      setMessages((prev) => [...prev, errorMsg])
    }
  }

  function submitMessage(event: FormEvent) {
    event.preventDefault()
    handleSendMessage()
  }

  async function startAdaptiveQuiz(topicId: number = 1) {
    setQuizOpen(true)
    setQuizLoading(true)
    setQuizResults({})
    setQuizAnswers({})
    try {
      const assessment = await generateAssessment(studentId, topicId, 3)
      setQuizData(assessment)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Failed to generate assessment quiz.")
    } finally {
      setQuizLoading(false)
    }
  }

  async function handleAnswerSubmit(questionId: number) {
    if (!quizData) return
    const answer = quizAnswers[questionId]
    if (!answer || !answer.trim()) return

    setSubmittingQ((prev) => ({ ...prev, [questionId]: true }))
    try {
      const evalRes = await submitAssessmentAnswer(
        studentId,
        quizData.assessment_id,
        questionId,
        answer.trim(),
      )
      setQuizResults((prev) => ({
        ...prev,
        [questionId]: {
          is_correct: evalRes.is_correct,
          feedback: evalRes.feedback,
          correct_answer: evalRes.correct_answer,
        },
      }))
      await loadLearnerInsights()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Failed to record student answer.")
    } finally {
      setSubmittingQ((prev) => ({ ...prev, [questionId]: false }))
    }
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
      if (event.key === "Escape") {
        setGraphFullscreen(false)
        setQuizOpen(false)
      }
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

  function renderFormattedAnswer(
    text: string,
    citations?: CitationItem[],
  ) {
    if (!citations || !citations.length) {
      return <p>{text}</p>
    }

    const parts = text.split(/(\[\d+\])/g)
    return (
      <div className="rendered-answer">
        {parts.map((part, idx) => {
          const match = part.match(/\[(\d+)\]/)
          if (match) {
            const cid = parseInt(match[1], 10)
            const targetCit = citations.find((c) => c.id === cid)
            return (
              <button
                className={`citation ${selectedCitationDetail?.id === cid ? "selected" : ""}`}
                key={`cit-${idx}`}
                onClick={() => targetCit && setSelectedCitationDetail(targetCit)}
                title={targetCit ? targetCit.label : `Citation [${cid}]`}
                type="button"
              >
                [{cid}]
              </button>
            )
          }
          return <span key={`txt-${idx}`}>{part}</span>
        })}
      </div>
    )
  }

  const graphNodes = useMemo(() => {
    const list = studyPath.length > 0 ? studyPath : [
      { topic_id: 1, title: "Graph Traversal", status: "ready_to_learn" },
      { topic_id: 2, title: "Shortest Paths", status: "blocked" },
      { topic_id: 3, title: "Spanning Trees", status: "blocked" },
    ]
    return list.map((item, idx) => ({
      id: item.title,
      topicId: item.topic_id,
      x: 70 + (idx % 3) * 105,
      y: 65 + Math.floor(idx / 3) * 75,
      kind: item.status === "mastered" ? "core" : item.status === "remediation" ? "minor" : "related",
      r: 10,
    }))
  }, [studyPath])

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

          <div className="module-group active-module">
            <button className="module-title">
              <span>01</span>
              <strong>{course?.title || "Core Syllabus"}</strong>
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
        </div>
      </aside>

      <section className="learning-panel">
        <header className="learning-header">
          <div className="breadcrumb">
            <span>{course?.subject || "Course"}</span>
            <i>/</i>
            <span>Module 01</span>
            <i>/</i>
            <strong>{selectedConcept}</strong>
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
              aria-label="Start adaptive quiz"
              className="icon-button"
              onClick={() => startAdaptiveQuiz(1)}
              title="Launch Adaptive Quiz"
            >
              <Icon name="spark" />
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
          {uploadError && (
            <div className="response-error" role="alert">
              <Icon name="warning" size={15} />
              <span>
                <strong>System Notice</strong>
                {uploadError}
              </span>
              <button onClick={() => setUploadError("")}>Dismiss</button>
            </div>
          )}

          {messages.length === 0 ? (
            <div className="conversation-empty">
              <span className="empty-kicker">{course?.subject || "COURSE"} · ADAPTIVE TUTOR</span>
              <h2>What would you like to understand?</h2>
              <p>
                Ask a concept question, explore algorithms, or launch an adaptive quiz
                grounded in your verified course materials.
              </p>
              <div>
                {[
                  "Explain breadth-first search",
                  "Compare BFS and DFS",
                  "Quiz me on graph traversal",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => {
                      if (prompt.startsWith("Quiz me")) {
                        startAdaptiveQuiz(1)
                      } else {
                        handleSendMessage(prompt)
                      }
                    }}
                  >
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

              {messages.map((msg) => (
                <div key={msg.id}>
                  {msg.role === "user" ? (
                    <div className="user-message">
                      <div className="speaker">You</div>
                      <p>{msg.content}</p>
                    </div>
                  ) : (
                    <article className="tutor-response">
                      <div className="response-content">
                        {renderFormattedAnswer(msg.content, msg.citations)}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="follow-up">
                            <span>Grounded Sources</span>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                              {msg.citations.map((c) => (
                                <button
                                  className={`citation-pill ${selectedCitationDetail?.id === c.id ? "selected" : ""}`}
                                  key={c.id}
                                  onClick={() => setSelectedCitationDetail(c)}
                                  type="button"
                                >
                                  [{c.id}] {c.location}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                        {!msg.is_grounded && msg.out_of_scope && (
                          <p className="footnote" style={{ color: "#b45309", marginTop: "8px" }}>
                            Notice: This query is outside the verified coverage of the course materials.
                          </p>
                        )}
                      </div>
                    </article>
                  )}
                </div>
              ))}

              {responseStatus === "generating" && (
                <div className="new-message">
                  <div className="thinking" aria-live="polite">
                    <span className="thinking-dots">
                      <i />
                      <i />
                      <i />
                    </span>
                    Reading across local course materials & synthesizing answer...
                  </div>
                </div>
              )}

              {responseStatus === "error" && (
                <div className="response-error" role="alert">
                  <Icon name="warning" size={15} />
                  <span>
                    <strong>Response interrupted</strong>
                    Failed to generate grounded answer.
                  </span>
                  <button onClick={() => handleSendMessage()}>Retry</button>
                </div>
              )}
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
              placeholder="Ask a question about this course or topic…"
              rows={1}
              value={message}
            />
            <div className="composer-actions">
              <button
                aria-label="Attach a material"
                className="attach-button"
                onClick={() => startAdaptiveQuiz(1)}
                title="Launch Adaptive Quiz"
                type="button"
              >
                <Icon name="spark" />
              </button>
              <span>Grounded in local 384-dim embeddings & Gemini</span>
              <button
                aria-label="Send message"
                className="send-button"
                disabled={!message.trim() || responseStatus === "generating"}
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
            title="Topic mastery"
          >
            <span className="rail-metric">{averageMastery}</span>
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
            <svg
              aria-label="Concept dependency map"
              className="graph"
              style={{ transform: `scale(${graphZoom})` }}
              viewBox="0 0 350 200"
            >
              {graphNodes.map((node) => {
                const isSelected = selectedConcept === node.id
                return (
                  <g
                    className={`node ${node.kind} ${isSelected ? "selected" : ""}`}
                    key={node.id}
                    onClick={() => setSelectedConcept(node.id)}
                    role="button"
                    tabIndex={0}
                  >
                    {isSelected && (
                      <circle className="node-ring" cx={node.x} cy={node.y} r={node.r + 7} />
                    )}
                    <circle cx={node.x} cy={node.y} r={node.r} />
                    <text x={node.x + 12} y={node.y + 3}>
                      {node.id}
                    </text>
                  </g>
                )
              })}
            </svg>
            <div className="docked-graph-controls">
              <button
                aria-label="Zoom out"
                onClick={() => setGraphZoom((zoom) => Math.max(0.75, zoom - 0.1))}
              >
                <Icon name="minus" size={13} />
              </button>
              <button aria-label="Reset graph view" onClick={() => setGraphZoom(1)}>
                <Icon name="reset" size={12} />
              </button>
              <button
                aria-label="Zoom in"
                onClick={() => setGraphZoom((zoom) => Math.min(1.4, zoom + 0.1))}
              >
                <Icon name="plus" size={13} />
              </button>
            </div>
          </div>

          {selectedCitationDetail ? (
            <div className="concept-focus">
              <span className="concept-dot" />
              <div>
                <small>SOURCE CITATION</small>
                <strong>{selectedCitationDetail.label}</strong>
                <p>Location: {selectedCitationDetail.location}</p>
                {selectedCitationDetail.text_snippet && (
                  <p style={{ fontStyle: "italic", marginTop: "3px" }}>
                    “{selectedCitationDetail.text_snippet}…”
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="concept-focus">
              <span className="concept-dot" />
              <div>
                <small>SELECTED CONCEPT</small>
                <strong>{selectedConcept}</strong>
                <p>Status: Adaptive learning path active</p>
              </div>
            </div>
          )}
        </section>

        <button
          aria-label="Resize graph and mastery panels"
          className="vertical-resize-handle"
          onPointerDown={beginVerticalResize}
          title="Drag to resize"
        />

        <section className={`progress-section ${masteryOpen ? "" : "minimized"}`}>
          <button
            className="mastery-toggle"
            onClick={() => setMasteryOpen((open) => !open)}
          >
            <div>
              <span className="eyebrow">THIS COURSE</span>
              <h2>Topic mastery</h2>
            </div>
            <span className="mastery-live">
              <i /> Live Tracking
            </span>
            <Icon name="chevron" size={14} />
          </button>

          <div className="mastery-content">
            <div className="mastery-overview">
              <div className="mastery-copy">
                <strong>{averageMastery}%</strong>
                <span>Overall Course Mastery</span>
              </div>
              <div className="mastery-bar">
                <span style={{ width: `${averageMastery}%` }} />
              </div>
              <span className="mastery-note">
                {studyPath.length} topics tracked in syllabus
              </span>
            </div>

            <div className="progress-list">
              {studyPath.map((item) => {
                const pct = Math.round(item.mastery_score * 100)
                const isMastered = item.status === "mastered"
                const isWeak = item.status === "remediation"
                return (
                  <button
                    className={`progress-item ${selectedConcept === item.title ? "selected" : ""}`}
                    key={item.topic_id}
                    onClick={() => {
                      setSelectedConcept(item.title)
                      startAdaptiveQuiz(item.topic_id)
                    }}
                  >
                    <span className={`status-icon ${isMastered ? "good" : isWeak ? "weak" : "current"}`}>
                      {isMastered ? <Icon name="check" size={12} /> : isWeak ? <Icon name="warning" size={12} /> : <Icon name="spark" size={12} />}
                    </span>
                    <div>
                      <strong>{item.title}</strong>
                      <span>
                        {item.status.toUpperCase()} · {pct}% Mastery
                      </span>
                    </div>
                    <span className="status-text">{pct}%</span>
                  </button>
                )
              })}

              {weakTopics.length > 0 && (
                <div style={{ marginTop: "12px", padding: "8px", background: "#fef3c7", borderRadius: "4px" }}>
                  <small style={{ fontWeight: 600, color: "#92400e" }}>RECOMMENDED REMEDIATION</small>
                  {weakTopics.map((w) => (
                    <div key={w.topic_id} style={{ fontSize: "10.5px", marginTop: "4px", color: "#78350f" }}>
                      • {w.title} (Deficit: {Math.round(w.deficit * 100)}%)
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button className="continue-link" onClick={() => startAdaptiveQuiz(1)}>
              <span>Test your understanding</span>
              <Icon name="arrow" size={15} />
            </button>
          </div>
        </section>
      </aside>

      {quizOpen && (
        <div
          aria-label="Adaptive Assessment Quiz"
          className="graph-overlay"
          role="dialog"
          style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
        >
          <div
            className="fullscreen-graph"
            style={{ maxWidth: "680px", maxHeight: "88vh", borderRadius: "8px", overflow: "hidden" }}
          >
            <header>
              <div>
                <span className="eyebrow">ADAPTIVE ASSESSMENT</span>
                <h2>{quizData?.topic_title || "Topic Quiz"}</h2>
              </div>
              <button className="exit-fullscreen" onClick={() => setQuizOpen(false)}>
                <Icon name="close" size={16} /> Close
              </button>
            </header>

            <div style={{ padding: "20px", overflowY: "auto", flex: 1 }}>
              {quizLoading ? (
                <div style={{ padding: "40px", textAlign: "center" }}>
                  <div className="processing-icon" style={{ margin: "0 auto 12px" }}>
                    <span />
                  </div>
                  <strong>Generating adaptive assessment questions...</strong>
                  <p style={{ color: "var(--muted)", fontSize: "12px", marginTop: "4px" }}>
                    Synthesizing questions from course chunks and matching your mastery level.
                  </p>
                </div>
              ) : quizData ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
                  {quizData.questions.map((q, idx) => {
                    const result = quizResults[q.id]
                    const currentAnswer = quizAnswers[q.id] || ""
                    const isSubmitting = submittingQ[q.id]

                    return (
                      <div
                        key={q.id}
                        style={{
                          padding: "16px",
                          border: "1px solid var(--line)",
                          borderRadius: "6px",
                          background: "#ffffff",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                          <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--sage-dark)" }}>
                            QUESTION {idx + 1} · {q.question_type.toUpperCase()} ({q.difficulty})
                          </span>
                          {result && (
                            <span
                              style={{
                                fontSize: "11px",
                                fontWeight: 700,
                                color: result.is_correct ? "#15803d" : "#b91c1c",
                              }}
                            >
                              {result.is_correct ? "✓ Correct" : "✗ Incorrect"}
                            </span>
                          )}
                        </div>

                        <p style={{ fontSize: "13.5px", fontWeight: 500, marginBottom: "12px" }}>
                          {q.prompt}
                        </p>

                        {q.question_type === "MCQ" && q.options && (
                          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "12px" }}>
                            {q.options.map((opt) => (
                              <button
                                key={opt}
                                onClick={() => !result && setQuizAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                                style={{
                                  padding: "9px 12px",
                                  textAlign: "left",
                                  borderRadius: "4px",
                                  border: "1px solid",
                                  borderColor: currentAnswer === opt ? "var(--teal)" : "#e5e7eb",
                                  background: currentAnswer === opt ? "var(--sage-faint)" : "#fafafa",
                                  fontWeight: currentAnswer === opt ? 600 : 400,
                                  cursor: result ? "default" : "pointer",
                                }}
                                type="button"
                              >
                                {opt}
                              </button>
                            ))}
                          </div>
                        )}

                        {q.question_type !== "MCQ" && (
                          <div style={{ marginBottom: "12px" }}>
                            <input
                              disabled={Boolean(result)}
                              onChange={(e) =>
                                setQuizAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                              }
                              placeholder="Enter your answer..."
                              style={{
                                width: "100%",
                                padding: "8px 10px",
                                border: "1px solid #d1d5db",
                                borderRadius: "4px",
                              }}
                              type="text"
                              value={currentAnswer}
                            />
                          </div>
                        )}

                        {!result ? (
                          <button
                            className="button-primary compact"
                            disabled={!currentAnswer.trim() || isSubmitting}
                            onClick={() => handleAnswerSubmit(q.id)}
                            style={{ alignSelf: "flex-start" }}
                            type="button"
                          >
                            {isSubmitting ? "Evaluating..." : "Submit Answer"}
                          </button>
                        ) : (
                          <div
                            style={{
                              marginTop: "8px",
                              padding: "10px",
                              borderRadius: "4px",
                              fontSize: "12px",
                              background: result.is_correct ? "#f0fdf4" : "#fef2f2",
                              color: result.is_correct ? "#166534" : "#991b1b",
                            }}
                          >
                            <strong>{result.feedback}</strong>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div>No quiz generated.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {graphFullscreen && (
        <div aria-label="Concept map fullscreen" className="graph-overlay" role="dialog">
          <div className="fullscreen-graph">
            <header>
              <div>
                <span className="eyebrow">{course?.subject || "Course"}</span>
                <h2>Concept map</h2>
              </div>
              <button className="exit-fullscreen" onClick={() => setGraphFullscreen(false)}>
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
              <button className="export-button" onClick={() => setGraphFullscreen(false)}>
                <Icon name="download" size={14} />
                Close View
              </button>
            </div>

            <div className="fullscreen-canvas">
              <div className="outline-tree">
                <strong>{course?.title || "Course Outline"}</strong>
                <div>
                  {studyPath.map((item) => (
                    <div key={item.topic_id} style={{ marginBottom: "10px" }}>
                      <span>{item.title}</span>
                      <small style={{ display: "block" }}>
                        {item.status.toUpperCase()} · {Math.round(item.mastery_score * 100)}% Mastery
                      </small>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
