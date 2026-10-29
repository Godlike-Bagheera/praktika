import { useAuth } from '../AuthContext';
import ReportToast from './ReportToast';

export default function ReportToastWrapper() {
  const { isAdmin } = useAuth();
  return <ReportToast isAdmin={isAdmin} />;
}
