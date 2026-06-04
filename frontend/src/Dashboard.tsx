// Import for type checking
import {
  apiUrl,
  checkPluginVersion,
  type InvenTreePluginContext,
  useMonitorDataOutput
} from '@inventreedb/ui';
import { ActionIcon, Group, Space, Title, Tooltip } from '@mantine/core';
import { IconClipboardList } from '@tabler/icons-react';
import { useState } from 'react';

/**
 * Render a custom dashboard item with the provided context
 * Refer to the InvenTree documentation for the context interface
 * https://docs.inventree.org/en/stable/extend/plugins/ui/#plugin-context
 */
function ComponentShortfallDashboardItem({
  context
}: {
  context: InvenTreePluginContext;
}) {
  const [outputId, setOutputId] = useState<number | undefined>(undefined);

  useMonitorDataOutput({
    api: context.api,
    queryClient: context.queryClient,
    id: outputId,
    title: 'Generating shortfall report'
  });

  const generateReport = context.forms.create({
    title: 'Generate Shortfall Report',
    url: apiUrl('/plugin/component-shortfall/shortfall/'),
    fields: {
      category: {},
      include_build_orders: {},
      include_sales_orders: {},
      horizon_months: {},
      max_bom_depth: {}
    },
    successMessage: null,
    onFormSuccess: (response) => {
      setOutputId(response.output?.pk);
    }
  });

  return (
    <>
      {generateReport.modal}
      <Group gap='xs' justify='space-between'>
        <Title c={context.theme?.primaryColor} order={5}>
          Component Shortfall Report
        </Title>
        <Space />
        <Tooltip label={'Generate Report'}>
          <ActionIcon
            onClick={() => generateReport.open()}
            variant='transparent'
          >
            <IconClipboardList />
          </ActionIcon>
        </Tooltip>
      </Group>
    </>
  );
}

// This is the function which is called by InvenTree to render the actual dashboard
//  component
export function renderComponentShortfallDashboardItem(
  context: InvenTreePluginContext
) {
  checkPluginVersion(context);
  return <ComponentShortfallDashboardItem context={context} />;
}
