import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Table, Card, Typography, Button, Tag, Space, Badge, Statistic, Row, Col } from 'antd';
import { ReloadOutlined, WifiOutlined, UserOutlined, LaptopOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getActiveHosts, getKerioStatus } from '../api/kerio';
import type { ActiveHost } from '../api/kerio';

const ActiveUsers = () => {
  const queryClient = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ['kerio-status'],
    queryFn: () => getKerioStatus().then((r) => r.data),
    refetchInterval: 30000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['active-hosts'],
    queryFn: () => getActiveHosts().then((r) => r.data),
    refetchInterval: 15000,
  });

  const hosts = data?.hosts || [];
  const authenticatedHosts = hosts.filter((h) => h.user?.name);

  const columns = [
    {
      title: 'User',
      key: 'user',
      render: (_: unknown, r: ActiveHost) => (
        <div>
          <div style={{ fontWeight: 500 }}>
            {r.user?.name || <Typography.Text type="secondary">Unauthenticated</Typography.Text>}
          </div>
          {r.name && <Typography.Text type="secondary" style={{ fontSize: 12 }}>{r.name}</Typography.Text>}
        </div>
      ),
    },
    {
      title: 'IP Address',
      key: 'ip',
      render: (_: unknown, r: ActiveHost) => (
        <Space size={4}>
          {r.ipAddress || '-'}
          {r.ipAddressFromDHCP && <Tag color="blue" style={{ fontSize: 10 }}>DHCP</Tag>}
        </Space>
      ),
      width: 160,
    },
    {
      title: 'MAC Address',
      dataIndex: 'macAddress',
      key: 'mac',
      render: (mac: string) => <code style={{ fontSize: 12 }}>{mac || '-'}</code>,
      width: 160,
    },
    {
      title: 'Connections',
      dataIndex: 'connections',
      key: 'conn',
      width: 100,
      render: (c: number) => c || 0,
    },
    {
      title: 'Login Time',
      dataIndex: 'loginTime',
      key: 'login',
      width: 150,
      render: (t: string) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: (_: unknown, r: ActiveHost) => (
        <Badge status={r.user?.name ? 'success' : 'default'} text={r.user?.name ? 'Online' : 'Guest'} />
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <WifiOutlined style={{ color: '#0d9488', marginRight: 8 }} />
          Active Users
        </Typography.Title>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['active-hosts'] });
            queryClient.invalidateQueries({ queryKey: ['kerio-status'] });
          }}
        >
          Refresh
        </Button>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Kerio Control"
              valueRender={() => (
                <Tag color={status?.connected ? 'green' : 'red'}>
                  {status?.connected ? 'Connected' : 'Disconnected'}
                </Tag>
              )}
              prefix={<LaptopOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Authenticated Users"
              value={authenticatedHosts.length}
              prefix={<UserOutlined style={{ color: '#0d9488' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Total Hosts"
              value={hosts.length}
              prefix={<WifiOutlined style={{ color: '#06b6d4' }} />}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          {hosts.length} host(s) connected — auto-refreshes every 15s
        </Typography.Text>
        <Table
          columns={columns}
          dataSource={hosts}
          rowKey="macAddress"
          loading={isLoading}
          pagination={false}
          size="middle"
        />
      </Card>
    </div>
  );
};

export default ActiveUsers;
