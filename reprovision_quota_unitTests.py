import unittest
from xml.dom import minidom
from unittest.mock import MagicMock
from unittest.mock import patch

from reprovision_quota import getIntendedNPVR


class TestGetIntendedNPVR(unittest.TestCase):

    def testCustomerWithCorrectNPVR(self):
        """Test case: Customer has the right NPVR."""
        mock_customer_xml = """
    <Customer id="171669">
        <NPVRQuota>120000</NPVRQuota>
        <CustomerData>PartnerSystemID:66;Zip:6386;PartnerId:25;Source:QMC;CustomerAT:Cable</CustomerData>
        <SubscriptionProducts>
            <SubscriptionProduct id="134" />
            <SubscriptionProduct id="80" />
            <SubscriptionProduct id="88" />
            <SubscriptionProduct id="447" />
            <SubscriptionProduct id="957" />
        </SubscriptionProducts>
    </Customer>
        """

        # Parse mock XML
        customer_data = minidom.parseString(mock_customer_xml)
        customer_node = customer_data.getElementsByTagName("Customer")[0]
        mock_npvr_bundle_data = [(647, 250*60), (784, 500*60), (957, 2000*60)]

        # Call the function with mock data
        file_quota, specified_quota = getIntendedNPVR(customer_node, mock_npvr_bundle_data)

        # Assert the results
        self.assertEqual(file_quota, 120000)
        self.assertEqual(specified_quota, 120000)



    def testCustomerWithWrongNPVR(self):
        """Test case: Customer doesn't have the right NPVR."""
        mock_customer_xml = """
    <Customer id="171669">
        <NPVRQuota>7777</NPVRQuota>
        <CustomerData>PartnerSystemID:66;Zip:6386;PartnerId:25;Source:QMC;CustomerAT:Cable</CustomerData>
        <SubscriptionProducts>
            <SubscriptionProduct id="134" />
            <SubscriptionProduct id="80" />
            <SubscriptionProduct id="88" />
            <SubscriptionProduct id="447" />
            <SubscriptionProduct id="957" />
        </SubscriptionProducts>
    </Customer>
        """

        customer_data = minidom.parseString(mock_customer_xml)
        customer_node = customer_data.getElementsByTagName("Customer")[0]
        mock_npvr_bundle_data = [(647, 250*60), (784, 500*60), (957, 2000*60)]
        file_quota, specified_quota = getIntendedNPVR(customer_node, mock_npvr_bundle_data)

        self.assertEqual(file_quota, 7777)
        self.assertEqual(specified_quota, 120000)



    def testNoCustomerXML(self):
        """Test case: no XML is passed as 'Customer'."""
        mock_customer_xml = None
        mock_npvr_bundle_data = [(647, 250*60), (784, 500*60), (957, 2000*60)]

        with self.assertRaises(Exception):
            getIntendedNPVR(mock_customer_xml, mock_npvr_bundle_data)

    

    def testCustomerWithoutSubscriptions(self):
        """Test case: Customer doesn't have any subscriptions."""
        mock_customer_xml = """
    <Customer id="171669">
        <NPVRQuota>0</NPVRQuota>
        <CustomerData>PartnerSystemID:66;Zip:6386;PartnerId:25;Source:QMC;CustomerAT:Cable</CustomerData>
        <SubscriptionProducts></SubscriptionProducts>
    </Customer>
        """

        customer_data = minidom.parseString(mock_customer_xml)
        customer_node = customer_data.getElementsByTagName("Customer")[0]
        mock_npvr_bundle_data = [(647, 250*60), (784, 500*60), (957, 2000*60)]
        file_quota, specified_quota = getIntendedNPVR(customer_node, mock_npvr_bundle_data)

        self.assertEqual(specified_quota, 0)



    def testCustomerWithoutNPVR(self):
        """Test case: Customer doesn't have any NPVR."""
        mock_customer_xml = """
    <Customer id="171669">
        <CustomerData>PartnerSystemID:66;Zip:6386;PartnerId:25;Source:QMC;CustomerAT:Cable</CustomerData>
        <SubscriptionProducts>
            <SubscriptionProduct id="134" />
            <SubscriptionProduct id="80" />
            <SubscriptionProduct id="88" />
            <SubscriptionProduct id="447" />
            <SubscriptionProduct id="957" />
        </SubscriptionProducts>
    </Customer>
        """

        customer_data = minidom.parseString(mock_customer_xml)
        customer_node = customer_data.getElementsByTagName("Customer")[0]
        mock_npvr_bundle_data = [(647, 250*60), (784, 500*60), (957, 2000*60)]
        file_quota, specified_quota = getIntendedNPVR(customer_node, mock_npvr_bundle_data)

        self.assertEqual(file_quota, 0)
        self.assertEqual(specified_quota, 120000)



    def testSameProductExistsTwice(self):
        """Test case: Customer has the same product multiple times."""
        mock_customer_xml = """
    <Customer id="171669">
        <NPVRQuota>120000</NPVRQuota>
        <CustomerData>PartnerSystemID:66;Zip:6386;PartnerId:25;Source:QMC;CustomerAT:Cable</CustomerData>
        <SubscriptionProducts>
            <SubscriptionProduct id="134" />
            <SubscriptionProduct id="80" />
            <SubscriptionProduct id="134" />
            <SubscriptionProduct id="957" />
            <SubscriptionProduct id="957" />
        </SubscriptionProducts>
    </Customer>
        """

        customer_data = minidom.parseString(mock_customer_xml)
        customer_node = customer_data.getElementsByTagName("Customer")[0]
        mock_npvr_bundle_data = [(647, 250*60), (784, 500*60), (957, 2000*60)]
        file_quota, specified_quota = getIntendedNPVR(customer_node, mock_npvr_bundle_data)

        self.assertEqual(file_quota, 120000)
        self.assertEqual(specified_quota, 120000)
       


    @patch('sys.exit')
    def testBundleDataIsEmpty(self, mock_exit):
        """Test case: Bundle data is empty."""
        mock_customer_xml = """
    <Customer id="171669">
        <NPVRQuota>120000</NPVRQuota>
        <CustomerData>PartnerSystemID:66;Zip:6386;PartnerId:25;Source:QMC;CustomerAT:Cable</CustomerData>
        <SubscriptionProducts>
            <SubscriptionProduct id="134" />
            <SubscriptionProduct id="80" />
            <SubscriptionProduct id="88" />
            <SubscriptionProduct id="447" />
            <SubscriptionProduct id="957" />
        </SubscriptionProducts>
    </Customer>
        """

        customer_data = minidom.parseString(mock_customer_xml)
        customer_node = customer_data.getElementsByTagName("Customer")[0]
        mock_npvr_bundle_data = []

        getIntendedNPVR(customer_node, mock_npvr_bundle_data)
        mock_exit.assert_called_with(1)



    @patch('sys.exit')
    def testBundleDataIsMissing(self, mock_exit):
        """Test case: Bundle data is missing."""
        mock_customer_xml = """
    <Customer id="171669">
        <NPVRQuota>120000</NPVRQuota>
        <CustomerData>PartnerSystemID:66;Zip:6386;PartnerId:25;Source:QMC;CustomerAT:Cable</CustomerData>
        <SubscriptionProducts>
            <SubscriptionProduct id="134" />
            <SubscriptionProduct id="80" />
            <SubscriptionProduct id="88" />
            <SubscriptionProduct id="447" />
            <SubscriptionProduct id="957" />
        </SubscriptionProducts>
    </Customer>
        """

        customer_data = minidom.parseString(mock_customer_xml)
        customer_node = customer_data.getElementsByTagName("Customer")[0]
        mock_npvr_bundle_data = None

        getIntendedNPVR(customer_node, mock_npvr_bundle_data)
        mock_exit.assert_called_with(1)



if __name__ == '__main__':
    unittest.main()
