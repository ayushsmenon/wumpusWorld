import { Link } from "react-router-dom";
import { mockCourses } from "../data/mockCourses";

export function HomePage() {
  return (
    <div className="content-frame">
      <section className="hero">
        <p className="eyebrow">Your learning workspace</p>
        <h1>Make room for better understanding.</h1>
        <p className="hero-copy">
          Return to a course, pick up where you left off, and build a clearer
          picture of what you know.
        </p>
      </section>

      <section aria-labelledby="courses-heading" className="section-block">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Keep learning</p>
            <h2 id="courses-heading">Your courses</h2>
          </div>
          <span className="section-count">{mockCourses.length} courses</span>
        </div>
        <div className="course-grid">
          {mockCourses.map((course) => (
            <Link className="course-card" key={course.id} to={`/courses/${course.id}`}>
              <div className="course-card-top">
                <span className="course-kicker">{course.code}</span>
                <span aria-hidden="true" className="course-arrow">
                  ↗
                </span>
              </div>
              <h3>{course.title}</h3>
              <p>{course.description}</p>
              <div className="progress-row">
                <span>{course.progress}% complete</span>
                <span>{course.lastStudied}</span>
              </div>
              <div className="progress-track" aria-label={`${course.progress}% complete`}>
                <span style={{ width: `${course.progress}%` }} />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
