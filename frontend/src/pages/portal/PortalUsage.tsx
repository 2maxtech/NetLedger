import { useQuery } from '@tanstack/react-query';
import { Card, Typography, Table, Space, Spin, Select } from 'antd';
import { ArrowLeftOutlined, WifiOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { getPortalUsage, getPortalSessions } from '../../api/portal';
import dayjs from 'dayjs';

const formatBytes = (bytes: number) => {
  if (!bytes) return '0 B';
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1073741824).toFixed(2)} GB`;
};

const PortalUsage = () => {
  const [days, setDays] = useState(30);

  const { data: usage, isLoading } = useQuery({
    queryKey: ['portal-usage', days],
    queryFn: () => getPortalUsage(days).then((r) => r.data),
  });

  const { data: sessions } = useQuery({
    queryKey: ['portal-sessions'],
    queryFn: () => getPortalSessions({ size: 10 }).then((r) => r.data),
  });

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const usageColumns = [
    { title: 'Date', dataIndex: 'date', key: 'date' },
    { title: 'Downloaded', key: 'in', render: (_: unknown, r: any) => formatBytes(r.bytes_in) },
    { title: 'Uploaded', key: 'out', render: (_: unknown, r: any) => formatBytes(r.bytes_out) },
    { title: 'Peak Down', dataIndex: 'peak_download_mbps', key: 'pd', render: (v: string) => `${v} Mbps` },
    { title: 'Peak Up', dataIndex: 'peak_upload_mbps', key: 'pu', render: (v: string) => `${v} Mbps` },
  ];

  const sessionColumns = [
    { title: 'IP Address', dataIndex: 'ip_address', key: 'ip' },
    { title: 'MAC', dataIndex: 'mac_address', key: 'mac' },
    { title: 'Started', dataIndex: 'started_at', key: 'start', render: (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm') },
    { title: 'Ended', dataIndex: 'ended_at', key: 'end', render: (d: string | null) => d ? dayjs(d).format('YYYY-MM-DD HH:mm') : 'Active' },
    { title: 'Downloaded', key: 'in', render: (_: unknown, r: any) => formatBytes(r.bytes_in) },
    { title: 'Uploaded', key: 'out', render: (_: unknown, r: any) => formatBytes(r.bytes_out) },
  ];

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Link to="/portal"><ArrowLeftOutlined /> Back to Dashboard</Link>
      </Space>
      <Typography.Title level={4}><WifiOutlined style={{ color: '#e8700a' }} /> My Usage</Typography.Title>

      <Card title="Bandwidth Usage" extra={
        <Select value={days} onChange={setDays} style={{ width: 120 }}>
          <Select.Option value={7}>Last 7 days</Select.Option>
          <Select.Option value={30}>Last 30 days</Select.Option>
          <Select.Option value={90}>Last 90 days</Select.Option>
        </Select>
      }>
        <Table columns={usageColumns} dataSource={usage || []} rowKey="date" pagination={false} />
      </Card>

      <Card title="Session History" style={{ marginTop: 16 }}>
        <Table columns={sessionColumns} dataSource={sessions || []} rowKey="id" pagination={false} />
      </Card>
    </div>
  );
};

export default PortalUsage;
