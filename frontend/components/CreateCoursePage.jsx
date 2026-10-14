import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createCourse } from "../lib/api";

export function CreateCoursePage() {
  const [form, setForm] = useState({ title: "", description: "", subject: "" });
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!form.title.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await createCourse(form.title, form.subject, form.description);
      setSubmitted(true);
      const newId = res?.course?.id || "1";
      navigate(`/courses/${newId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create course");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="content-frame form-frame">
      <Link className="back-link" to="/">← Back to home</Link>
      <section className="form-intro">
        <p className="eyebrow">New learning space</p>
        <h1>Create a course</h1>
        <p className="hero-copy">Start with the context you want to study. You can add materials next.</p>
      </section>
      <form className="course-form" onSubmit={submit}>
        <label>
          Course title <span>Required</span>
          <input autoFocus maxLength={160} name="title" onChange={updateField} placeholder="e.g. Introductory Biology" value={form.title} />
        </label>
        <label>
          Subject or category <span>Optional</span>
          <input maxLength={100} name="subject" onChange={updateField} placeholder="e.g. Biology" value={form.subject} />
        </label>
        <label>
          Short description <span>Optional</span>
          <textarea maxLength={500} name="description" onChange={updateField} placeholder="What will you learn in this course?" rows={4} value={form.description} />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        {submitted && <p className="form-note" role="status">Course created successfully!</p>}
        <div className="form-actions">
          <Link className="button-secondary" to="/">Cancel</Link>
          <button className="button-primary" disabled={loading} type="submit">
            {loading ? "Creating..." : "Create course"}
          </button>
        </div>
      </form>
    </div>
  );
}
