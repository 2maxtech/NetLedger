import { useQuery } from '@tanstack/react-query';
import { Row, Col, Card, Typography, Statistic, Tag, Table, Progress, Space, Badge } from 'antd';
import {
  TeamOutlined, WifiOutlined, DollarOutlined, WarningOutlined,
  CloudServerOutlined, CheckCircleOutlined, PauseCircleOutlined,
  RiseOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { getDashboard } from '../api/network';

const formatBytes = (bytes: number) => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
};

const formatPeso = (amount: number) =>
  `₱${amount.toLocaleString('en-PH', { minimumFractionDigits: 2 })}`;

const Dashboard = () => {
  const { data } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => getDashboard().then((r) => r.data),
    refetchInterval: 5000,
  });

  const subs = data?.subscribers || { total: 0, active: 0, suspended: 0, disconnected: 0 };
  const billing = data?.billing || { mrr: 0, billed_this_month: 0, collected_this_month: 0, collection_rate: 0, overdue_count: 0, overdue_amount: 0 };
  const mt = data?.mikrotik || { connected: false, identity: '', uptime: '', cpu_load: '0', free_memory: 0, total_memory: 1, active_sessions: 0, interfaces: [], version: '' };
  const trend = data?.revenue_trend || [];
  const payments = data?.recent_payments || [];

  const memPercent = mt.total_memory > 0 ? Math.round((1 - mt.free_memory / mt.total_memory) * 100) : 0;
  const maxTrend = Math.max(...trend.map((t) => t.collected), 1);

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>Dashboard</Typography.Title>
        <Typography.Text type="secondary">
          {mt.connected ? (
            <Space>
              <Badge status="success" />
              {mt.identity} — RouterOS {mt.version} — up {mt.uptime}
            </Space>
          ) : (
            <Space><Badge status="error" />MikroTik disconnected</Space>
          )}
        </Typography.Text>
      </div>

      {/* Row 1: Subscriber Stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Subscribers"
              value={subs.total}
              prefix={<TeamOutlined style={{ color: '#e8700a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Active"
              value={subs.active}
              prefix={<CheckCircleOutlined style={{ color: '#10b981' }} />}
              suffix={subs.total > 0 ? <Typography.Text type="secondary" style={{ fontSize: 14 }}>{`/ ${subs.total}`}</Typography.Text> : null}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Suspended"
              value={subs.suspended}
              prefix={<PauseCircleOutlined style={{ color: '#f59e0b' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="PPPoE Online"
              value={mt.active_sessions}
              prefix={<WifiOutlined style={{ color: '#e8700a' }} />}
              suffix={subs.active > 0 ? <Typography.Text type="secondary" style={{ fontSize: 14 }}>{`/ ${subs.active}`}</Typography.Text> : null}
            />
          </Card>
        </Col>
      </Row>

      {/* Row 2: Revenue Stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Monthly Recurring Revenue"
              value={billing.mrr}
              prefix={<DollarOutlined style={{ color: '#e8700a' }} />}
              formatter={(val) => formatPeso(val as number)}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Collected This Month"
              value={billing.collected_this_month}
              prefix={<RiseOutlined style={{ color: '#10b981' }} />}
              formatter={(val) => formatPeso(val as number)}
            />
            {billing.billed_this_month > 0 && (
              <Progress
                percent={billing.collection_rate}
                size="small"
                strokeColor="#10b981"
                style={{ marginTop: 8 }}
                format={(p) => `${p}%`}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Billed This Month"
              value={billing.billed_this_month}
              prefix={<DollarOutlined style={{ color: '#64748b' }} />}
              formatter={(val) => formatPeso(val as number)}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Overdue"
              value={billing.overdue_count}
              prefix={<WarningOutlined style={{ color: '#ef4444' }} />}
              suffix={billing.overdue_amount > 0 ? <Typography.Text type="secondary" style={{ fontSize: 12 }}>{formatPeso(billing.overdue_amount)}</Typography.Text> : null}
            />
          </Card>
        </Col>
      </Row>

      {/* Row 3: MikroTik Health + Revenue Trend */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <CloudServerOutlined style={{ color: '#e8700a' }} />
                <span>MikroTik Router</span>
                <Tag color={mt.connected ? 'green' : 'red'}>{mt.connected ? 'Online' : 'Offline'}</Tag>
              </Space>
            }
            style={{ height: '100%' }}
          >
            <Row gutter={[16, 16]}>
              <Col span={8}>
                <div style={{ textAlign: 'center' }}>
                  <Progress
                    type="dashboard"
                    percent={Number(mt.cpu_load) || 0}
                    size={80}
                    strokeColor={Number(mt.cpu_load) > 80 ? '#ef4444' : '#e8700a'}
                  />
                  <div style={{ marginTop: 4, fontSize: 12, color: '#64748b' }}>CPU</div>
                </div>
              </Col>
              <Col span={8}>
                <div style={{ textAlign: 'center' }}>
                  <Progress
                    type="dashboard"
                    percent={memPercent}
                    size={80}
                    strokeColor={memPercent > 80 ? '#ef4444' : '#f9a825'}
                  />
                  <div style={{ marginTop: 4, fontSize: 12, color: '#64748b' }}>Memory</div>
                </div>
              </Col>
              <Col span={8}>
                <div style={{ textAlign: 'center' }}>
                  <Statistic
                    value={mt.active_sessions}
                    suffix="sessions"
                    valueStyle={{ fontSize: 24, color: '#e8700a' }}
                  />
                  <div style={{ fontSize: 12, color: '#64748b' }}>PPPoE Active</div>
                </div>
              </Col>
            </Row>
            {mt.interfaces.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <Typography.Text strong style={{ fontSize: 13 }}>Interface Traffic</Typography.Text>
                <Table
                  size="small"
                  pagination={false}
                  dataSource={mt.interfaces}
                  rowKey="name"
                  style={{ marginTop: 8 }}
                  columns={[
                    {
                      title: 'Interface',
                      dataIndex: 'name',
                      render: (name: string, r: any) => (
                        <Space>
                          <Badge status={r.running ? 'success' : 'default'} />
                          {name}
                        </Space>
                      ),
                    },
                    { title: 'RX', dataIndex: 'rx_bytes', render: (v: number) => formatBytes(v), align: 'right' as const },
                    { title: 'TX', dataIndex: 'tx_bytes', render: (v: number) => formatBytes(v), align: 'right' as const },
                  ]}
                />
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <RiseOutlined style={{ color: '#10b981' }} />
                <span>Revenue Trend (6 Months)</span>
              </Space>
            }
            style={{ height: '100%' }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {trend.map((t) => (
                <div key={t.month} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Typography.Text style={{ width: 60, fontSize: 12, color: '#64748b' }}>
                    {dayjs(t.month + '-01').format('MMM YY')}
                  </Typography.Text>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        height: 24,
                        width: `${Math.max((t.collected / maxTrend) * 100, 2)}%`,
                        background: 'linear-gradient(90deg, #e8700a, #f9a825)',
                        borderRadius: 4,
                        display: 'flex',
                        alignItems: 'center',
                        paddingLeft: 8,
                        minWidth: 40,
                      }}
                    >
                      <Typography.Text style={{ fontSize: 11, color: '#fff', fontWeight: 600 }}>
                        {t.collected > 0 ? formatPeso(t.collected) : ''}
                      </Typography.Text>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Recent Payments */}
            <div style={{ marginTop: 24 }}>
              <Typography.Text strong style={{ fontSize: 13 }}>Recent Payments</Typography.Text>
              {payments.length > 0 ? (
                <Table
                  size="small"
                  pagination={false}
                  dataSource={payments}
                  rowKey="id"
                  style={{ marginTop: 8 }}
                  columns={[
                    {
                      title: 'Amount',
                      dataIndex: 'amount',
                      render: (v: string) => <span style={{ fontWeight: 500, color: '#10b981' }}>{formatPeso(parseFloat(v))}</span>,
                    },
                    {
                      title: 'Method',
                      dataIndex: 'method',
                      render: (m: string) => <Tag>{m}</Tag>,
                    },
                    {
                      title: 'Date',
                      dataIndex: 'received_at',
                      render: (d: string) => d ? dayjs(d).format('MMM D, h:mm A') : '-',
                    },
                  ]}
                />
              ) : (
                <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                  No payments this month
                </Typography.Text>
              )}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
