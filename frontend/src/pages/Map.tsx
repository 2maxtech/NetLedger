import { Card, Typography } from 'antd';
import { GlobalOutlined } from '@ant-design/icons';

const Map = () => (
  <div>
    <div style={{ marginBottom: 16 }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        <GlobalOutlined style={{ color: '#e8700a', marginRight: 8 }} />
        Network Map
      </Typography.Title>
    </div>
    <Card>
      <div style={{ textAlign: 'center', padding: '60px 0' }}>
        <GlobalOutlined style={{ fontSize: 48, color: '#e8700a', marginBottom: 16 }} />
        <Typography.Title level={4} style={{ color: '#6b7280' }}>
          Map view requires Leaflet.js — coming soon
        </Typography.Title>
        <Typography.Text type="secondary">
          Install <code>leaflet</code> and <code>react-leaflet</code> to enable the interactive map.
        </Typography.Text>
      </div>
    </Card>
  </div>
);

export default Map;
