import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { CoursePage } from "../components/CoursePage";
import { CreateCoursePage } from "../components/CreateCoursePage";
import { HomePage } from "../components/HomePage";
import CourseWorkspace from "../components/CourseWorkspace";

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <AppShell>
            <HomePage />
          </AppShell>
        }
      />
      <Route path="/courses/:courseId" element={<CoursePage />} />
      <Route path="/courses/new" element={<AppShell><CreateCoursePage /></AppShell>} />
      <Route path="/workspace" element={<CourseWorkspace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
