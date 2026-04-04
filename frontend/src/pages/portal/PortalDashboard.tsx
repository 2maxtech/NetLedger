import { useQuery } from '@tanstack/react-query';
import { Card, Typography, Row, Col, Table, Statistic, Descriptions, Spin, Button } from 'antd';
import { WifiOutlined, DollarOutlined, CloudOutlined, LogoutOutlined } from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import dayjs from 'dayjs';
import StatusTag from '../../components/StatusTag';
import { getPortalDashboard } from '../../api/portal';

const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1073741824).toFixed(2)} GB`;
};

const PortalDashboard = () => {
  const navigate = useNavigate();
  const customerStr = localStorage.getItem('portal_customer');
  const customer = customerStr ? JSON.parse(customerStr) : null;

  const { data, isLoading } = useQuery({
    queryKey: ['portal-dashboard'],
    queryFn: () => getPortalDashboard().then((r) => r.data),
  });

  const logout = () => {
    localStorage.removeItem('portal_token');
    localStorage.removeItem('portal_customer');
    navigate('/portal/login');
  };

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Typography.Title level={3} style={{ margin: 0, color: '#e8700a' }}>
            <WifiOutlined /> NetLedger Portal
          </Typography.Title>
          <Typography.Text type="secondary">Welcome, {customer?.full_name}</Typography.Text>
        </div>
        <div>
          <Link to="/portal/invoices" style={{ marginRight: 16 }}>My Invoices</Link>
          <Link to="/portal/usage" style={{ marginRight: 16 }}>Usage</Link>
          <Button icon={<LogoutOutlined />} onClick={logout}>Logout</Button>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic title="Account Status" valueRender={() => <StatusTag status={data?.status || ''} />} />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic title="Current Plan" value={data?.plan?.name || 'None'} prefix={<CloudOutlined />} suffix={data?.plan ? `${data.plan.download_mbps}/${data.plan.upload_mbps} Mbps` : ''} />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic title="Outstanding Balance" value={`₱${Number(data?.outstanding_balance || 0).toFixed(2)}`} prefix={<DollarOutlined />} valueStyle={{ color: Number(data?.outstanding_balance || 0) > 0 ? '#ef4444' : '#10b981' }} />
          </Card>
        </Col>
      </Row>

      {data?.session && (
        <Card title="Active Session" style={{ marginTop: 16 }}>
          <Descriptions column={2}>
            <Descriptions.Item label="IP Address">{data.session.ip_address}</Descriptions.Item>
            <Descriptions.Item label="Connected Since">{dayjs(data.session.started_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
            <Descriptions.Item label="Downloaded">{formatBytes(data.session.bytes_in)}</Descriptions.Item>
            <Descriptions.Item label="Uploaded">{formatBytes(data.session.bytes_out)}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <Card title="Recent Invoices" style={{ marginTop: 16 }} extra={<Link to="/portal/invoices">View All</Link>}>
        <Table
          dataSource={data?.recent_invoices || []}
          rowKey="id"
          pagination={false}
          columns={[
            { title: 'Amount', key: 'amount', render: (_, r) => `₱${Number(r.amount).toFixed(2)}` },
            { title: 'Due Date', dataIndex: 'due_date', key: 'due' },
            { title: 'Status', dataIndex: 'status', key: 'status', render: (s: string) => <StatusTag status={s} /> },
          ]}
        />
      </Card>
    </div>
  );
};

export default PortalDashboard;
