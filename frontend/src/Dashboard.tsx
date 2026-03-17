// Import for type checking
import {
  ApiEndpoints,
  ApiFormFieldSet,
  apiUrl,
  checkPluginVersion,
  type InvenTreePluginContext,
  useMonitorDataOutput
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
      max_bom_depth: {}
    },
    successMessage: null,
    onFormSuccess: (response) => {
      setOutputId(response.output?.pk);
    }
  });

  const [importOpened, setImportOpened] = useState<boolean>(false);

  const [selectedSession, setSelectedSession] = useState<number | undefined>(
    undefined
  );

  const fields: ApiFormFieldSet = {
    data_file: {},
    model_type: {},
    update_records: {},
  };

  const importData = context.forms.create({
    title: 'Import Data',
    url: ApiEndpoints.import_session_list,
    fields: fields,
    onFormSuccess: (response: any) => {
      setSelectedSession(response.pk);
      setImportOpened(true);
    }
  });

  return (
    <>
      {importData.modal}
      {generateReport.modal}
      <Stack gap='xs'>
        <Text size='lg'>Generate Shortfall Report</Text>
        <Button
          leftSection={<IconClipboardList />}
          onClick={() => importData.open()}
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
