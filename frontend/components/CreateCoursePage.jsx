import { useState } from "react";
import { Link } from "react-router-dom";

export function CreateCoursePage() {
  const [form, setForm] = useState({ title: "", description: "", subject: "" });
  const [submitted, setSubmitted] = useState(false);

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (form.title.trim()) setSubmitted(true);
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
        {submitted && <p className="form-note" role="status">Course creation will be connected in a future step.</p>}
        <div className="form-actions">
          <Link className="button-secondary" to="/">Cancel</Link>
          <button className="button-primary" type="submit">Create course</button>
        </div>
      </form>
    </div>
  );
}
