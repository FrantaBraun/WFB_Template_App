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
import Teams from "./pages/Teams"
import TeamDetail from "./pages/TeamDetail"
import AcceptInvitation from "./pages/AcceptInvitation"
import ApiDocs from "./pages/ApiDocs"
import NewApiDoc from "./pages/NewApiDoc"
import ApiDocDetail from "./pages/ApiDocDetail"
import Collections from "./pages/Collections"
import CollectionDetail from "./pages/CollectionDetail"
import Integrations from "./pages/Integrations"
import IntegrationDetail from "./pages/IntegrationDetail"
import { useEnabledModules } from "./modules/registry"


function App() {
  const modules = useEnabledModules()

  return (<Layout modules={modules}>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/account" element={<Account />} />
      <Route path="/teams" element={<Teams />} />
      <Route path="/teams/invitations/:token" element={<AcceptInvitation />} />
      <Route path="/teams/:id" element={<TeamDetail />} />
      <Route path="/api-docs" element={<ApiDocs />} />
      <Route path="/api-docs/new" element={<NewApiDoc />} />
      <Route path="/api-docs/:id" element={<ApiDocDetail />} />
      <Route path="/collections" element={<Collections />} />
      <Route path="/collections/:id" element={<CollectionDetail />} />
      <Route path="/integrations" element={<Integrations />} />
      <Route path="/integrations/:id" element={<IntegrationDetail />} />
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
    </Routes>

  </Layout>
  )
}

export default App
