import { Link, useParams } from "react-router-dom";
import { getCourse } from "../data/mockCourses";

export function CoursePage() {
  const { courseId } = useParams();
  const course = getCourse(courseId);

  if (!course) {
    return (
      <div className="content-frame state-panel">
        <p className="eyebrow">Course unavailable</p>
        <h1>We could not find that course.</h1>
        <Link className="text-link" to="/">
          Return home
        </Link>
      </div>
    );
  }

  return (
    <div className="content-frame">
      <Link className="back-link" to="/">
        ← Back to home
      </Link>
      <section className="course-intro">
        <p className="eyebrow">{course.code}</p>
        <h1>{course.title}</h1>
        <p className="hero-copy">{course.description}</p>
      </section>
      <section className="workspace-placeholder" aria-labelledby="workspace-heading">
        <p className="eyebrow">Course workspace</p>
        <h2 id="workspace-heading">Your study space is ready for the next layer.</h2>
        <p>
          This foundation keeps the route, course identity, and layout boundary
          ready for the Figma-led tutor interface.
        </p>
      </section>
    </div>
  );
}
