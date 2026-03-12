// Import for type checking
import {
  apiUrl,
  checkPluginVersion,
  type InvenTreePluginContext,
  monitorDataOutput
} from '@inventreedb/ui';
import { Button, Stack, Text } from '@mantine/core';
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

  monitorDataOutput({
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
    },
    successMessage: null,
    onFormSuccess: (response) => {
      setOutputId(response.output?.pk);
    }
  });

  return (
    <>
      {generateReport.modal}
      <Stack gap='xs'>
        <Text size='lg'>Generate Shortfall Report</Text>
        <Button
          leftSection={<IconClipboardList />}
          onClick={() => generateReport.open()}
        >
          Generate Report
        </Button>
      </Stack>
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
