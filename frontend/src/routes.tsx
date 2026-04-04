import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import React, { Suspense, lazy } from 'react';
import AppLayout from './components/Layout/AppLayout';
import Login from './pages/Login';
import { useAuth, AuthProvider } from './hooks/useAuth';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const CustomerList = lazy(() => import('./pages/customers/CustomerList'));
const CustomerDetail = lazy(() => import('./pages/customers/CustomerDetail'));
const Plans = lazy(() => import('./pages/Plans'));
const Invoices = lazy(() => import('./pages/billing/Invoices'));
const Payments = lazy(() => import('./pages/billing/Payments'));
const Users = lazy(() => import('./pages/system/Users'));
const SystemStatus = lazy(() => import('./pages/system/SystemStatus'));
const Logs = lazy(() => import('./pages/system/Logs'));

const ActiveUsers = lazy(() => import('./pages/ActiveUsers'));

const PortalLogin = lazy(() => import('./pages/portal/PortalLogin'));
const PortalDashboard = lazy(() => import('./pages/portal/PortalDashboard'));
const PortalInvoices = lazy(() => import('./pages/portal/PortalInvoices'));
const PortalUsage = lazy(() => import('./pages/portal/PortalUsage'));

const Loading = () => <div style={{ display: 'flex', justifyContent: 'center', padding: 100 }}><Spin size="large" /></div>;

const PrivateRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <Loading />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

const RootLayout = () => (
  <AuthProvider>
    <PrivateRoute><AppLayout /></PrivateRoute>
  </AuthProvider>
);

const LoginWrapper = () => (
  <AuthProvider><Login /></AuthProvider>
);

const wrap = (Component: React.LazyExoticComponent<React.ComponentType>) => (
  <Suspense fallback={<Loading />}><Component /></Suspense>
);

export const router = createBrowserRouter([
  { path: '/login', element: <LoginWrapper /> },
  { path: '/portal/login', element: wrap(PortalLogin) },
  { path: '/portal', element: wrap(PortalDashboard) },
  { path: '/portal/invoices', element: wrap(PortalInvoices) },
  { path: '/portal/usage', element: wrap(PortalUsage) },
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: wrap(Dashboard) },
      { path: 'customers', element: wrap(CustomerList) },
      { path: 'customers/:id', element: wrap(CustomerDetail) },
      { path: 'plans', element: wrap(Plans) },
      { path: 'billing/invoices', element: wrap(Invoices) },
      { path: 'billing/payments', element: wrap(Payments) },
      { path: 'active-users', element: wrap(ActiveUsers) },
      { path: 'system/users', element: wrap(Users) },
      { path: 'system/status', element: wrap(SystemStatus) },
      { path: 'system/logs', element: wrap(Logs) },
    ],
  },
]);
