"""validate prosper.test_utils.schema_utils"""
import os

import pytest
import helpers

import prosper.test_utils.schema_utils as schema_utils
import prosper.test_utils.exceptions as exceptions


@pytest.fixture
def mongo_fixture(tmpdir):
    """helper for making testmode mongo context managers

    Args:
        tmpdir: PyTest magic

    Returns:
        schema_utils.MongoContextManager: in tinydb mode

    """
    mongo_context = schema_utils.MongoContextManager(
        helpers.TEST_CONFIG,
        _testmode_filepath=tmpdir,
        _testmode=True,
    )
    return mongo_context


class TestMongoContextManager:
    """validate expected behavior for MongoContextManager"""
    demo_data = [
        {'butts': True, 'many': 10},
        {'butts': False, 'many': 100},
    ]
    def test_mongo_context_testmode(self, tmpdir):
        """test with _testmode enabled"""
        mongo_context = schema_utils.MongoContextManager(
            helpers.TEST_CONFIG,
            _testmode=True,
            _testmode_filepath=tmpdir,
        )

        with mongo_context as t_mongo:
            t_mongo['test_collection'].insert(self.demo_data)

        with mongo_context as t_mongo:
            data = t_mongo['test_collection'].find_one({'butts': True})

        assert data['many'] == 10

    def test_mongo_context_prodmode(self):
        """test against real mongo"""
        if not helpers.can_connect_to_mongo(helpers.TEST_CONFIG):
            pytest.xfail('no mongo credentials')

        mongo_context = schema_utils.MongoContextManager(
            helpers.TEST_CONFIG,
        )

        with mongo_context as mongo:
            mongo['test_collection'].insert(self.demo_data)

        with mongo_context as _:
            data = mongo['test_collection'].find_one({'butts': True})

        assert data['many'] == 10

class TestFetchLatestSchema:
    fake_schema_table = [
        {'schema_group':'test', 'schema_name':'fake.schema', 'version':'1.0.0',
         'schema':{'result':'NOPE'}},
        {'schema_group':'test', 'schema_name':'fake.schema', 'version':'1.1.0',
         'schema':{'result':'NOPE'}},
        {'schema_group':'test', 'schema_name':'fake.schema', 'version':'1.1.1',
         'schema':{'result':'YUP'}},
        {'schema_group':'not_test', 'schema_name':'fake.schema', 'version':'1.1.2',
         'schema':{'result':'NOPE'}},
    ]
    def test_fetch_latest_version(self, mongo_fixture):
        """try to find latest schema"""
        collection_name = 'fake_schema_table'

        with mongo_fixture as t_mongo:
            t_mongo[collection_name].insert(self.fake_schema_table)

        with mongo_fixture as t_mongo:
            latest_schema = schema_utils.fetch_latest_schema(
                'fake.schema',
                'test',
                t_mongo[collection_name]
            )

        assert latest_schema['schema'] == {'result': 'YUP'}
        assert latest_schema['version'] == '1.1.1'

    def test_fetch_latest_version_empty(self, mongo_fixture):
        """make sure function returns expected for no content"""
        collection_name = 'blank_schema_table'

        with mongo_fixture as t_mongo:
            latest_schema = schema_utils.fetch_latest_schema(
                'fake.schema',
                'test',
                t_mongo[collection_name]
            )

        assert latest_schema['schema'] == {}
        assert latest_schema['version'] == '1.0.0'

class TestCompareSchemas:
    """validate expected behavior for compare_schemas()"""
    base_schema = helpers.load_schema_from_file('base_schema.json')
    minor_change = helpers.load_schema_from_file('minor_schema_change.json')
    major_removed_value = helpers.load_schema_from_file('major_items_removed.json')
    major_values_changed = helpers.load_schema_from_file('major_values_changed.json')
    unhandled_diff = set(helpers.load_schema_from_file('unhandled_diff.json'))

    def test_compare_schemas_happypath(self):
        """make sure equivalence works as expected"""
        status = schema_utils.compare_schemas(
            self.base_schema,
            self.base_schema
        )

        assert status == schema_utils.Update.no_update

    def test_compare_schemas_minor(self):
        """make sure minor updates are tagged as such"""
        status = schema_utils.compare_schemas(
            self.base_schema,
            self.minor_change
        )

        assert status == schema_utils.Update.minor

    def test_compare_schemas_major(self):
        """make sure major updates are tagged as such"""
        status = schema_utils.compare_schemas(
            self.base_schema,
            self.major_removed_value
        )

        assert status == schema_utils.Update.major

        status = schema_utils.compare_schemas(
            self.base_schema,
            self.major_values_changed
        )

        assert status == schema_utils.Update.major

    def test_compare_schemas_empty(self):
        """make sure empty case signals first-run"""
        status = schema_utils.compare_schemas(
            {},
            self.base_schema,
        )

        assert status == schema_utils.Update.first_run

    def test_compare_schemas_error(self):
        """make sure raises for really screwed up case"""
        pytest.xfail('compare_schemas raise case not working yet')
        with pytest.raises(exceptions.UnhandledDiff):
            status = schema_utils.compare_schemas(
                self.base_schema,
                self.unhandled_diff
            )

