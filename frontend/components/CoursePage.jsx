import { Link, useParams } from "react-router-dom";
import CourseWorkspace from "./CourseWorkspace";
import { getExampleCourse } from "../data/mockCourses";

export function CoursePage() {
  const { courseId } = useParams();
  const course = getExampleCourse(courseId);

  if (course) {
    return <CourseWorkspace course={course} />;
  }

  return (
    <div className="content-frame state-panel">
      <p className="eyebrow">Course workspace</p>
      <h1>This course is not available yet.</h1>
      <Link className="text-link" to="/">
        Return home
      </Link>
    </div>
  );
}
