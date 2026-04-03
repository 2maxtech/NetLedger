import { Tag } from 'antd';

const statusColors: Record<string, string> = {
  active: '#10b981', online: '#10b981', paid: '#10b981', sent: '#10b981',
  suspended: '#f59e0b', overdue: '#f59e0b', pending: '#0d9488',
  disconnected: '#ef4444', failed: '#ef4444',
  terminated: '#9ca3af', void: '#9ca3af',
};

const StatusTag = ({ status }: { status: string }) => (
  <Tag color={statusColors[status] || '#9ca3af'} style={{ textTransform: 'capitalize' }}>
    {status}
  </Tag>
);

export default StatusTag;
