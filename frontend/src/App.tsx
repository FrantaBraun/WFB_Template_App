/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Top-level route table: wraps every page in the shared Layout (nav + chrome)
// and declares the app's client-side routes.
import { Route, Routes } from "react-router-dom"
import HomePage from "./pages/HomePage"
import Layout from "./components/Layout"
import Account from "./pages/Account"
import Consent from "./pages/Consent"
import ConsentRejected from "./pages/ConsentRejected"
import Login from "./pages/Login"
import Register from "./pages/Register"
import OAuthCallback from "./pages/OAuthCallback"
import Version from "./pages/Version"
import ReleaseNews from "./pages/ReleaseNews"
import AdminHome from "./pages/admin/AdminHome"
import AdminPagesList from "./pages/admin/AdminPagesList"
import AdminPageForm from "./pages/admin/AdminPageForm"
import AdminArticlesList from "./pages/admin/AdminArticlesList"
import AdminArticleForm from "./pages/admin/AdminArticleForm"
import { useEnabledModules } from "./modules/registry"


function App() {
  const modules = useEnabledModules()

  return (<Layout modules={modules}>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/account" element={<Account />} />
      <Route path="/oauth/callback" element={<OAuthCallback />} />
      <Route path="/consent" element={<Consent />} />
      <Route path="/consent-rejected" element={<ConsentRejected />} />
      {/* Publicly accessible, hidden from regular nav */}
      <Route path="/version" element={<Version />} />
      <Route path="/release-news" element={<ReleaseNews />} />
      {/* Admin-only - each page gates itself via useRequireAdmin */}
      <Route path="/admin" element={<AdminHome />} />
      <Route path="/admin/pages" element={<AdminPagesList />} />
      <Route path="/admin/pages/new" element={<AdminPageForm />} />
      <Route path="/admin/pages/:id/edit" element={<AdminPageForm />} />
      <Route path="/admin/articles" element={<AdminArticlesList />} />
      <Route path="/admin/articles/new" element={<AdminArticleForm />} />
      <Route path="/admin/articles/:id/edit" element={<AdminArticleForm />} />
      {/* Enabled feature modules (see src/modules/) contribute their own routes here */}
      {modules.flatMap((module) =>
        module.routes.map((route) => (
          <Route key={`${module.key}:${route.path}`} path={route.path} element={route.element} />
        )),
      )}
    </Routes>

  </Layout>
  )
}

export default App
