import { Row, Col, Card, Typography } from 'antd';
import { TeamOutlined, WifiOutlined, DollarOutlined, WarningOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import ReactECharts from 'echarts-for-react';
import StatCard from '../components/StatCard';
import { getCustomers } from '../api/customers';

const Dashboard = () => {
  const { data: customersData } = useQuery({
    queryKey: ['customers-count'],
    queryFn: () => getCustomers({ page: 1, page_size: 1 }),
  });

  const totalCustomers = customersData?.data?.total ?? 0;

  const trafficChartOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'] },
    yAxis: { type: 'value', name: 'Mbps' },
    series: [
      { name: 'Download', type: 'line', smooth: true, areaStyle: { opacity: 0.3 }, data: [20, 15, 30, 65, 80, 55, 35], itemStyle: { color: '#0d9488' } },
      { name: 'Upload', type: 'line', smooth: true, areaStyle: { opacity: 0.3 }, data: [5, 3, 8, 15, 20, 12, 8], itemStyle: { color: '#f59e0b' } },
    ],
  };

  return (
    <div>
      <Typography.Title level={4}>Dashboard</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="Online Customers" value="--" prefix={<WifiOutlined />} valueStyle={{ color: '#10b981' }} />
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
            <Typography.Text type="secondary">Kerio Control integration pending</Typography.Text>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
