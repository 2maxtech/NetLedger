import { Row, Col, Card, Typography, Progress, Alert } from 'antd';
import { TeamOutlined, WifiOutlined, DollarOutlined, WarningOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import ReactECharts from 'echarts-for-react';
import StatCard from '../components/StatCard';
import { getCustomers } from '../api/customers';
import { getSessions } from '../api/pppoe';
import { getSystemStats } from '../api/gateway';

const Dashboard = () => {
  const { data: customersData } = useQuery({
    queryKey: ['customers-count'],
    queryFn: () => getCustomers({ page: 1, page_size: 1 }),
  });

  const { data: sessionsData } = useQuery({
    queryKey: ['pppoe-sessions'],
    queryFn: getSessions,
    refetchInterval: 10000,
  });

  const { data: statsData, error: statsError } = useQuery({
    queryKey: ['system-stats'],
    queryFn: getSystemStats,
    refetchInterval: 5000,
  });

  const totalCustomers = customersData?.data?.total ?? 0;
  const onlineSessions = sessionsData?.data?.length ?? 0;
  const stats = statsData?.data;

  const trafficChartOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'] },
    yAxis: { type: 'value', name: 'Mbps' },
    series: [
      { name: 'Download', type: 'line', smooth: true, areaStyle: { opacity: 0.3 }, data: [20, 15, 30, 65, 80, 55, 35], itemStyle: { color: '#0d9488' } },
      { name: 'Upload', type: 'line', smooth: true, areaStyle: { opacity: 0.3 }, data: [5, 3, 8, 15, 20, 12, 8], itemStyle: { color: '#f59e0b' } },
    ],
  };

  const progressColor = (pct: number) => (pct < 60 ? '#10b981' : pct < 80 ? '#f59e0b' : '#ef4444');

  return (
    <div>
      <Typography.Title level={4}>Dashboard</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="Online Customers" value={onlineSessions} prefix={<WifiOutlined />} valueStyle={{ color: '#10b981' }} />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="Total Customers" value={totalCustomers} prefix={<TeamOutlined />} />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="Monthly Revenue" value="--" prefix={<DollarOutlined />} valueStyle={{ color: '#0d9488' }} />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="Overdue Invoices" value="--" prefix={<WarningOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card title="Network Traffic (Sample Data)">
            <ReactECharts option={trafficChartOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="System Health">
            {statsError ? (
              <Alert type="error" message="Gateway unreachable" showIcon />
            ) : stats ? (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <Typography.Text>CPU</Typography.Text>
                  <Progress percent={Math.round(stats.cpu_percent)} strokeColor={progressColor(stats.cpu_percent)} />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <Typography.Text>Memory</Typography.Text>
                  <Progress percent={Math.round(stats.memory_percent)} strokeColor={progressColor(stats.memory_percent)} />
                </div>
                <div>
                  <Typography.Text>Disk</Typography.Text>
                  <Progress percent={Math.round(stats.disk_percent)} strokeColor={progressColor(stats.disk_percent)} />
                </div>
              </div>
            ) : (
              <Typography.Text type="secondary">Loading...</Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
