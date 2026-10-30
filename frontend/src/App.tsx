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
import ForgotPassword from "./pages/ForgotPassword"
import ResetPassword from "./pages/ResetPassword"
import Register from "./pages/Register"
import OAuthCallback from "./pages/OAuthCallback"
import Version from "./pages/Version"
import ReleaseNews from "./pages/ReleaseNews"
import { useEnabledModules } from "./modules/registry"
import NotFound from "./pages/NotFound"


function App() {
  const modules = useEnabledModules()
  const isRegistrationAllowed = (import.meta.env.VITE_REGISTRATION_ALLOWED || 'true') === 'true';
  return (<Layout modules={modules}>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      {isRegistrationAllowed && <Route path="/register" element={<Register />} />}
      <Route path="/account" element={<Account />} />
      <Route path="/oauth/callback" element={<OAuthCallback />} />
      <Route path="/consent" element={<Consent />} />
      <Route path="/consent-rejected" element={<ConsentRejected />} />
      {/* Publicly accessible, hidden from regular nav */}
      <Route path="/version" element={<Version />} />
      <Route path="/release-news" element={<ReleaseNews />} />
      {/* Enabled feature modules (see src/modules/) contribute their own routes here */}
      {modules.flatMap((module) =>
        module.routes.map((route) => (
          <Route key={`${module.key}:${route.path}`} path={route.path} element={route.element} />
        )),
      )}
      <Route path="*" element={<NotFound />} />
    </Routes>

  </Layout>
  )
}

export default App
