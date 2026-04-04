import { Card, Typography } from 'antd';

const SystemStatus = () => {
  return (
    <div>
      <Typography.Title level={4}>System Status</Typography.Title>
      <Card>
        <Typography.Text type="secondary">Kerio Control integration pending. System metrics will be available once the Kerio adapter is connected.</Typography.Text>
      </Card>
    </div>
  );
};

export default SystemStatus;
