import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import TabsOnly from "./layouts/TabsOnly";
import General from "./pages/Dashboards/General";
import Estadisticas from "./pages/Dashboards/Estadisticas";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<TabsOnly />}>
          <Route path="/" element={<Navigate to="/general" replace />} />
          <Route path="/general" element={<General />} />
          <Route path="/estadisticas" element={<Estadisticas />} />
          <Route path="*" element={<Navigate to="/general" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
