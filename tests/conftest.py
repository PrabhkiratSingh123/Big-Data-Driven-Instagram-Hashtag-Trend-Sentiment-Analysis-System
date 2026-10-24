"""Pytest configuration and compatibility fixtures."""

import mongomock

# Compatibility patch for mongomock with PyMongo 4.9+ (which passes 'sort' to add_update)
_orig_add_update = mongomock.collection.BulkOperationBuilder.add_update

def _patched_add_update(self, filter, doc, multi, upsert, collation=None, array_filters=None, hint=None, sort=None):
    return _orig_add_update(self, filter, doc, multi, upsert, collation=collation, array_filters=array_filters, hint=hint)

mongomock.collection.BulkOperationBuilder.add_update = _patched_add_update
