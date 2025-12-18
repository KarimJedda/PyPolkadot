use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::sync::{Arc, OnceLock};
use subxt::ext::scale_value::Value;
use subxt::{client::OnlineClient, lightclient::LightClient as SubxtLightClient, PolkadotConfig};
use tokio::runtime::Runtime;

// Embedded chain specs for relay chains and parachains
const POLKADOT_RELAY_SPEC: &str = include_str!("../pypolkadot/chain_specs/polkadot.json");
const ASSET_HUB_POLKADOT_SPEC: &str = include_str!("../pypolkadot/chain_specs/asset-hub-polkadot.json");
const PASEO_RELAY_SPEC: &str = include_str!("../pypolkadot/chain_specs/paseo.raw.smol.json");
const PASEO_ASSET_HUB_SPEC: &str = include_str!("../pypolkadot/chain_specs/paseo-asset-hub.smol.json");

// Global tokio runtime (singleton pattern from subxt ffi-example)
static RUNTIME: OnceLock<Runtime> = OnceLock::new();

fn runtime() -> &'static Runtime {
    RUNTIME.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("Failed to create Tokio runtime")
    })
}

/// Custom error type for pysubxt
#[derive(Debug, thiserror::Error)]
pub enum PySubxtError {
    #[error("Light client error: {0}")]
    LightClient(String),
    #[error("Block error: {0}")]
    Block(String),
    #[error("Storage error: {0}")]
    Storage(String),
    #[error("Events error: {0}")]
    Events(String),
    #[error("Transaction error: {0}")]
    Transaction(String),
    #[error("Subscription ended")]
    SubscriptionEnded,
}

/// Convert a hex string to bytes (with or without 0x prefix)
fn hex_to_bytes(hex: &str) -> Result<Vec<u8>, String> {
    let hex = hex.strip_prefix("0x").unwrap_or(hex);
    hex::decode(hex).map_err(|e| format!("Invalid hex string: {}", e))
}

/// Convert a Python object to a scale_value::Value
fn py_to_scale_value(_py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<Value<()>> {
    // Handle different Python types
    if let Ok(s) = obj.extract::<String>() {
        // If it looks like a hex string (account ID, hash, etc.), convert to bytes
        if s.starts_with("0x") || (s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit())) {
            let bytes = hex_to_bytes(&s)
                .map_err(|e| PyRuntimeError::new_err(e))?;
            Ok(Value::from_bytes(bytes))
        } else {
            // Otherwise treat as string
            Ok(Value::string(s))
        }
    } else if let Ok(n) = obj.extract::<u128>() {
        Ok(Value::u128(n))
    } else if let Ok(n) = obj.extract::<i128>() {
        Ok(Value::i128(n))
    } else if let Ok(b) = obj.extract::<bool>() {
        Ok(Value::bool(b))
    } else if let Ok(bytes) = obj.extract::<Vec<u8>>() {
        Ok(Value::from_bytes(bytes))
    } else if obj.is_none() {
        Ok(Value::unnamed_variant("None", []))
    } else {
        Err(PyRuntimeError::new_err(format!(
            "Unsupported Python type for storage key: {}",
            obj.get_type().name()?
        )))
    }
}

/// Convert a scale_value::Value to a Python object via JSON
fn scale_value_to_py(py: Python<'_>, value: &Value<()>) -> PyResult<PyObject> {
    // Serialize to JSON, then parse as Python dict/value
    let json = serde_json::to_string(value)
        .map_err(|e| PyRuntimeError::new_err(format!("JSON serialization error: {}", e)))?;

    // Parse JSON into Python object
    let json_module = py.import_bound("json")?;
    let result = json_module.call_method1("loads", (json,))?;
    Ok(result.into())
}

impl From<PySubxtError> for PyErr {
    fn from(err: PySubxtError) -> PyErr {
        PyRuntimeError::new_err(err.to_string())
    }
}

/// A single finalized block
#[pyclass]
#[derive(Clone)]
pub struct Block {
    #[pyo3(get)]
    hash: String,
    #[pyo3(get)]
    number: u32,
}

#[pymethods]
impl Block {
    fn __repr__(&self) -> String {
        format!("Block(number={}, hash={})", self.number, self.hash)
    }

    fn __str__(&self) -> String {
        format!("Block #{}: {}", self.number, self.hash)
    }
}

/// A decoded runtime event
#[pyclass]
pub struct Event {
    /// The pallet that emitted this event (e.g., "Balances", "System")
    #[pyo3(get)]
    pallet: String,
    /// The event variant name (e.g., "Transfer", "NewAccount")
    #[pyo3(get)]
    name: String,
    /// The decoded event fields as a Python dict
    #[pyo3(get)]
    fields: PyObject,
    /// The index of this event in the block
    #[pyo3(get)]
    index: u32,
}

#[pymethods]
impl Event {
    fn __repr__(&self) -> String {
        format!("Event(pallet={}, name={}, index={})", self.pallet, self.name, self.index)
    }

    fn __str__(&self) -> String {
        format!("{}.{}", self.pallet, self.name)
    }
}

/// Block subscription iterator
#[pyclass]
pub struct BlockSubscription {
    receiver: std::sync::mpsc::Receiver<Result<Block, String>>,
}

#[pymethods]
impl BlockSubscription {
    fn __iter__(slf: PyRef<Self>) -> PyRef<Self> {
        slf
    }

    fn __next__(&self) -> PyResult<Option<Block>> {
        // Block waiting for the next block (holds GIL, but blocks come slowly ~6s)
        match self.receiver.recv() {
            Ok(Ok(block)) => Ok(Some(block)),
            Ok(Err(e)) => Err(PyRuntimeError::new_err(e)),
            Err(_) => Ok(None), // Channel closed, iteration ends
        }
    }
}

/// Python-exposed LightClient for connecting to Substrate/Polkadot chains
#[pyclass]
pub struct LightClient {
    inner: Arc<OnlineClient<PolkadotConfig>>,
    // Keep the light client alive for the duration
    _light_client: Arc<SubxtLightClient>,
}

#[pymethods]
impl LightClient {
    /// Connect to Asset Hub (mainnet or testnet).
    ///
    /// This will start a smoldot light client that connects to Asset Hub.
    /// Initial sync may take a moment.
    ///
    /// Args:
    ///     testnet: If True, connect to Paseo Asset Hub (testnet).
    ///              If False (default), connect to Asset Hub Polkadot (mainnet).
    ///
    /// Returns:
    ///     LightClient: A connected light client instance
    ///
    /// Raises:
    ///     RuntimeError: If connection fails
    #[new]
    #[pyo3(signature = (testnet=false))]
    fn new(py: Python<'_>, testnet: bool) -> PyResult<Self> {
        let (relay_spec, para_spec) = if testnet {
            (PASEO_RELAY_SPEC, PASEO_ASSET_HUB_SPEC)
        } else {
            (POLKADOT_RELAY_SPEC, ASSET_HUB_POLKADOT_SPEC)
        };

        py.allow_threads(|| {
            runtime().block_on(async {
                // First connect to relay chain
                let (light_client, _relay_rpc) = SubxtLightClient::relay_chain(relay_spec)
                    .map_err(|e| PySubxtError::LightClient(e.to_string()))?;

                // Then add parachain (Asset Hub)
                let para_rpc = light_client
                    .parachain(para_spec)
                    .map_err(|e| PySubxtError::LightClient(e.to_string()))?;

                let api = OnlineClient::<PolkadotConfig>::from_rpc_client(para_rpc)
                    .await
                    .map_err(|e| PySubxtError::LightClient(e.to_string()))?;

                Ok(LightClient {
                    inner: Arc::new(api),
                    _light_client: Arc::new(light_client),
                })
            })
        })
    }

    /// Connect using a custom chain spec JSON string.
    ///
    /// Args:
    ///     spec: JSON string containing the chain specification
    ///
    /// Returns:
    ///     LightClient: A connected light client instance
    ///
    /// Raises:
    ///     RuntimeError: If connection fails or chain spec is invalid
    #[staticmethod]
    fn from_chain_spec(py: Python<'_>, spec: &str) -> PyResult<Self> {
        let spec = spec.to_string();
        py.allow_threads(|| {
            runtime().block_on(async {
                let (light_client, rpc) = SubxtLightClient::relay_chain(spec.as_str())
                    .map_err(|e| PySubxtError::LightClient(e.to_string()))?;

                let api = OnlineClient::<PolkadotConfig>::from_rpc_client(rpc)
                    .await
                    .map_err(|e| PySubxtError::LightClient(e.to_string()))?;

                Ok(LightClient {
                    inner: Arc::new(api),
                    _light_client: Arc::new(light_client),
                })
            })
        })
    }

    /// Subscribe to finalized blocks.
    ///
    /// Returns an iterator that yields Block objects as they are finalized.
    /// The iterator will block waiting for each new block.
    ///
    /// Returns:
    ///     BlockSubscription: An iterator over finalized blocks
    ///
    /// Example:
    ///     >>> client = LightClient.polkadot()
    ///     >>> for block in client.subscribe_finalized():
    ///     ...     print(f"Block #{block.number}: {block.hash}")
    fn subscribe_finalized(&self, py: Python<'_>) -> PyResult<BlockSubscription> {
        let client = self.inner.clone();
        let (tx, rx) = std::sync::mpsc::channel();

        // Spawn background task to drive the subscription
        py.allow_threads(|| {
            runtime().spawn(async move {
                let mut stream = match client.blocks().subscribe_finalized().await {
                    Ok(s) => s,
                    Err(e) => {
                        let _ = tx.send(Err(format!("Failed to subscribe: {}", e)));
                        return;
                    }
                };

                while let Some(result) = stream.next().await {
                    let block_result = match result {
                        Ok(block) => Ok(Block {
                            hash: format!("{:?}", block.hash()),
                            number: block.number(),
                        }),
                        Err(e) => Err(format!("Block error: {}", e)),
                    };

                    if tx.send(block_result).is_err() {
                        break; // Receiver dropped
                    }
                }
            });
        });

        Ok(BlockSubscription { receiver: rx })
    }

    /// Get the latest finalized block.
    ///
    /// Returns:
    ///     Block: The latest finalized block
    ///
    /// Raises:
    ///     RuntimeError: If fetching the block fails
    fn get_finalized_block(&self, py: Python<'_>) -> PyResult<Block> {
        let client = self.inner.clone();
        py.allow_threads(|| {
            runtime().block_on(async {
                let block = client
                    .blocks()
                    .at_latest()
                    .await
                    .map_err(|e| PySubxtError::Block(e.to_string()))?;

                Ok(Block {
                    hash: format!("{:?}", block.hash()),
                    number: block.number(),
                })
            })
        })
    }

    /// Query a storage value at the latest finalized block.
    ///
    /// Args:
    ///     pallet: The pallet name (e.g., "System", "Balances")
    ///     entry: The storage entry name (e.g., "Account", "TotalIssuance")
    ///     keys: Optional list of keys for map storage items
    ///
    /// Returns:
    ///     The decoded storage value as a Python dict/value, or None if not found
    ///
    /// Example:
    ///     >>> client = LightClient.polkadot()
    ///     >>> # Query a plain storage value
    ///     >>> total = client.storage("Balances", "TotalIssuance", [])
    ///     >>> # Query a map storage value
    ///     >>> account = client.storage("System", "Account", ["0x...account_id"])
    #[pyo3(signature = (pallet, entry, keys=None))]
    fn storage(
        &self,
        py: Python<'_>,
        pallet: &str,
        entry: &str,
        keys: Option<Vec<Bound<'_, PyAny>>>,
    ) -> PyResult<Option<PyObject>> {
        let client = self.inner.clone();
        let pallet = pallet.to_string();
        let entry = entry.to_string();

        // Convert Python keys to scale_value::Value
        let scale_keys: Vec<Value<()>> = match keys {
            Some(k) => k
                .iter()
                .map(|obj| py_to_scale_value(py, obj))
                .collect::<PyResult<Vec<_>>>()?,
            None => vec![],
        };

        // Query storage
        let result = py.allow_threads(|| {
            runtime().block_on(async move {
                // Create dynamic storage address (keys passed to fetch in new API)
                let storage_query = subxt::dynamic::storage(&pallet, &entry);

                // Get storage at latest block
                let storage = client
                    .storage()
                    .at_latest()
                    .await
                    .map_err(|e| PySubxtError::Storage(e.to_string()))?;

                // Fetch the value (keys passed as second argument now)
                let value = storage
                    .fetch(&storage_query, scale_keys)
                    .await
                    .map_err(|e| PySubxtError::Storage(e.to_string()))?;

                // StorageValue wraps the result directly - decode it
                let decoded = value
                    .decode()
                    .map_err(|e| PySubxtError::Storage(e.to_string()))?;
                Ok::<_, PySubxtError>(Some(decoded))
            })
        })?;

        // Convert result to Python
        match result {
            Some(value) => Ok(Some(scale_value_to_py(py, &value)?)),
            None => Ok(None),
        }
    }

    /// Get all events for a block.
    ///
    /// Args:
    ///     block_hash: Optional block hash (hex string). If None, uses latest finalized block.
    ///     pallet: Optional pallet name to filter events (e.g., "Balances")
    ///     name: Optional event name to filter (e.g., "Transfer")
    ///
    /// Returns:
    ///     List of Event objects
    ///
    /// Example:
    ///     >>> client = LightClient.polkadot()
    ///     >>> # Get all events for latest block
    ///     >>> events = client.events()
    ///     >>> for event in events:
    ///     ...     print(f"{event.pallet}.{event.name}")
    ///     >>> # Filter for specific events
    ///     >>> transfers = client.events(pallet="Balances", name="Transfer")
    #[pyo3(signature = (block_hash=None, pallet=None, name=None))]
    fn events(
        &self,
        py: Python<'_>,
        block_hash: Option<&str>,
        pallet: Option<&str>,
        name: Option<&str>,
    ) -> PyResult<Vec<Event>> {
        let client = self.inner.clone();
        let block_hash_bytes: Option<[u8; 32]> = match block_hash {
            Some(h) => {
                let bytes = hex_to_bytes(h)
                    .map_err(|e| PyRuntimeError::new_err(e))?;
                if bytes.len() != 32 {
                    return Err(PyRuntimeError::new_err("Block hash must be 32 bytes"));
                }
                let mut arr = [0u8; 32];
                arr.copy_from_slice(&bytes);
                Some(arr)
            }
            None => None,
        };
        let pallet_filter = pallet.map(|s| s.to_string());
        let name_filter = name.map(|s| s.to_string());

        // Fetch events
        let events_data = py.allow_threads(|| {
            runtime().block_on(async move {
                // Get events at specified block or latest
                let events = match block_hash_bytes {
                    Some(hash) => {
                        let hash = subxt::utils::H256::from(hash);
                        client
                            .events()
                            .at(hash)
                            .await
                            .map_err(|e| PySubxtError::Events(e.to_string()))?
                    }
                    None => {
                        client
                            .events()
                            .at_latest()
                            .await
                            .map_err(|e| PySubxtError::Events(e.to_string()))?
                    }
                };

                // Collect events with their data
                let mut result: Vec<(String, String, Value<()>, u32)> = Vec::new();
                let mut index = 0u32;

                for event in events.iter() {
                    let event = event.map_err(|e| PySubxtError::Events(e.to_string()))?;

                    let event_pallet = event.pallet_name().to_string();
                    let event_name = event.variant_name().to_string();

                    // Apply filters
                    if let Some(ref filter) = pallet_filter {
                        if &event_pallet != filter {
                            index += 1;
                            continue;
                        }
                    }
                    if let Some(ref filter) = name_filter {
                        if &event_name != filter {
                            index += 1;
                            continue;
                        }
                    }

                    // Decode fields
                    let fields = event
                        .decode_as_fields::<Value<()>>()
                        .map_err(|e| PySubxtError::Events(e.to_string()))?;

                    result.push((event_pallet, event_name, fields, index));
                    index += 1;
                }

                Ok::<_, PySubxtError>(result)
            })
        })?;

        // Convert to Python Event objects
        let mut py_events = Vec::new();
        for (pallet, name, fields, index) in events_data {
            let fields_py = scale_value_to_py(py, &fields)?;
            py_events.push(Event {
                pallet,
                name,
                fields: fields_py,
                index,
            });
        }

        Ok(py_events)
    }

    /// Submit a pre-signed extrinsic to the network.
    ///
    /// The extrinsic must already be signed and SCALE-encoded. Use an external
    /// library (e.g., `substrateinterface`, `py-sr25519-bindings`) for signing.
    ///
    /// Args:
    ///     extrinsic: Hex-encoded signed extrinsic (with or without 0x prefix)
    ///
    /// Returns:
    ///     Transaction hash (hex string with 0x prefix)
    ///
    /// Raises:
    ///     RuntimeError: If submission fails (invalid tx, network error, etc.)
    ///
    /// Example:
    ///     >>> # Sign with external library
    ///     >>> signed_tx = external_signer.sign(payload)
    ///     >>> # Submit via light client
    ///     >>> tx_hash = client.submit(signed_tx.hex())
    ///     >>> print(f"Submitted: {tx_hash}")
    fn submit(&self, py: Python<'_>, extrinsic: &str) -> PyResult<String> {
        let client = (*self.inner).clone();

        // Decode hex to bytes
        let tx_bytes = hex_to_bytes(extrinsic)
            .map_err(|e| PyRuntimeError::new_err(e))?;

        // Submit the transaction
        let tx_hash = py.allow_threads(|| {
            runtime().block_on(async move {
                use subxt::tx::SubmittableTransaction;

                // Create submittable transaction from raw bytes
                let tx = SubmittableTransaction::from_bytes(client, tx_bytes);

                // Submit and get hash
                let hash = tx
                    .submit()
                    .await
                    .map_err(|e| PySubxtError::Transaction(e.to_string()))?;

                Ok::<_, PySubxtError>(format!("0x{}", hex::encode(hash.0)))
            })
        })?;

        Ok(tx_hash)
    }
}

/// Python module definition
#[pymodule]
fn _pypolkadot(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<LightClient>()?;
    m.add_class::<BlockSubscription>()?;
    m.add_class::<Block>()?;
    m.add_class::<Event>()?;
    Ok(())
}
