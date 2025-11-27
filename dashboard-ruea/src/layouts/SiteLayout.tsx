import { Outlet, NavLink } from "react-router-dom";

export default function SiteLayout() {
  return (
    <>
      {/* Barra GOV simple */}
      <div className="govbar">
        <div className="container small">
          <span className="govlogo">GOV.CO</span>
          <nav className="govlinks">
            <a>Opciones de Accesibilidad</a>
            <a>Idioma</a>
            <a>Inicia sesión</a>
            <a>Regístrate</a>
          </nav>
        </div>
      </div>

      {/* Cabecera principal */}
      <header className="siteheader">
        <div className="container head">
          <div className="brand">
            <img src="/logo-alcaldia.png" alt="Alcaldía de Medellín" />
            <div className="brand-txt">
              <div className="brand-title">Alcaldía de Medellín</div>
              <div className="brand-sub">Ciencia, Tecnología e Innovación</div>
            </div>
          </div>
          <nav className="mainnav">
            <a>Participa</a>
            <a>Transparencia</a>
            <a>Servicios a la Ciudadanía</a>
            <a>Sala de prensa</a>
            <a>Impuestos</a>
            <NavLink to="/dashboards/general" className={({isActive})=> isActive ? "active" : ""}>
              Dashboards
            </NavLink>
          </nav>
        </div>
      </header>

      <Outlet />

      <footer className="sitefooter">
        <div className="container small">
          © {new Date().getFullYear()} Alcaldía de Medellín — Módulo de Dashboards
        </div>
      </footer>
    </>
  );
}
