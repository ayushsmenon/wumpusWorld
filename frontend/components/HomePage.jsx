import { Link } from "react-router-dom";
import { exampleCourses } from "../data/mockCourses";

export function HomePage() {
  return (
    <div className="content-frame">
      <section className="hero">
        <p className="eyebrow">Your learning workspace</p>
        <h1>Welcome to your learning workspace.</h1>
      </section>

      <section aria-labelledby="courses-heading" className="section-block">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Keep learning</p>
            <h2 id="courses-heading">Your courses</h2>
          </div>
          <Link className="button-primary compact" to="/courses/new">Create course</Link>
        </div>
        <div className="course-grid">
          {exampleCourses.map((course) => (
            <Link className="course-card" key={course.id} to={`/courses/${course.id}`}>
              <div className="course-card-top">
                <span className="course-kicker">{course.subject}</span>
                <span aria-hidden="true" className="course-arrow">↗</span>
              </div>
              <h3>{course.title}</h3>
              <p>{course.description}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
