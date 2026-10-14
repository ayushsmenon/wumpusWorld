export const exampleCourses = [
  {
    id: "1",
    subject: "CS 201",
    title: "Data Structures & Algorithms",
    description: "Master foundational and advanced data structures, graph traversals, and shortest path algorithms.",
    materials: [
      { filename: "graph-traversal.pdf", file_type: "pdf", status: "parsed", unit_count: 24 },
      { filename: "search-and-trees.pptx", file_type: "pptx", status: "parsed", unit_count: 18 },
    ],
  },
  {
    id: "2",
    subject: "AI 301",
    title: "Artificial Intelligence & Search",
    description: "Explore heuristic search, state-space exploration, and adaptive agent reasoning.",
    materials: [
      { filename: "state-space-search.pdf", file_type: "pdf", status: "parsed", unit_count: 30 },
    ],
  },
];

export function getExampleCourse(courseId) {
  return exampleCourses.find((c) => String(c.id) === String(courseId)) || exampleCourses[0];
}
