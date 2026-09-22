/**
 * Copyright 2018-present, Facebook, Inc. All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

'use strict';

const crypto = require('crypto');

// Verify that the callback came from Facebook.
// This is intended to be used as the `verify` callback for body-parser's json()
// middleware: body_parser.json({ verify: verifyRequestSignature })
function verifyRequestSignature(req, res, buf) {
    var signature = req.headers['x-hub-signature'];

    if (!signature) {
        throw new Error("Couldn't find 'x-hub-signature' in headers.");
    } else {
        var elements = signature.split('=');
        var signatureHash = elements[1];
        var expectedHash = crypto
            .createHmac('sha1', process.env.APP_SECRET)
            .update(buf)
            .digest('hex');
        if (signatureHash != expectedHash) {
            throw new Error("Couldn't validate the request signature.");
        }
    }
}

module.exports = { verifyRequestSignature };
