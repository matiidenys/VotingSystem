// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

/**
 * @title IWhitelistRegistry
 * @notice Interface for interacting with external registries.
 */
interface IWhitelistRegistry {
    /**
     * @notice Checks if a user is listed in the registry.
     * @param _user The address to check.
     * @return True if the user is whitelisted, false otherwise.
     */
    function isWhitelisted(address _user) external view returns (bool);
}

/**
 * @title WhitelistRegistry
 * @notice A reusable registry for employees or members.
 * @dev Designed to be deployed once and used across multiple voting contracts.
 */
contract WhitelistRegistry {
    /// @notice Address of the registry administrator.
    address public admin;

    /// @notice Mapping to store whitelisted status of addresses.
    mapping(address => bool) public whitelist;

    /// @notice Emitted when a user's status changes.
    event RegistryUpdated(address indexed user, bool status);

    /**
     * @notice Sets the deployer as the initial admin.
     */
    constructor() {
        admin = msg.sender;
    }

    modifier onlyAdmin() {
        require(msg.sender == admin, "Caller is not the admin");
        _;
    }

    /**
     * @notice Adds a single user to the registry.
     * @param _user Address to add.
     */
    function addToRegistry(address _user) external onlyAdmin {
        whitelist[_user] = true;
        emit RegistryUpdated(_user, true);
    }

    /**
     * @notice Adds multiple users to the registry in a single transaction.
     * @param _users Array of addresses to add.
     */
    function addManyToRegistry(address[] calldata _users) external onlyAdmin {
        for (uint256 i = 0; i < _users.length; i++) {
            whitelist[_users[i]] = true;
            emit RegistryUpdated(_users[i], true);
        }
    }

    /**
     * @notice Removes a single user from the registry.
     * @param _user Address to remove.
     */
    function removeFromRegistry(address _user) external onlyAdmin {
        whitelist[_user] = false;
        emit RegistryUpdated(_user, false);
    }

    /**
     * @notice Removes multiple users from the registry.
     * @param _users Array of addresses to remove.
     */
    function removeManyFromRegistry(address[] calldata _users) external onlyAdmin {
        for (uint256 i = 0; i < _users.length; i++) {
            whitelist[_users[i]] = false;
            emit RegistryUpdated(_users[i], false);
        }
    }

    /**
     * @notice Checks if a specific user is in the registry.
     * @param _user Address to check.
     * @return True if whitelisted.
     */
    function isWhitelisted(address _user) external view returns (bool) {
        return whitelist[_user];
    }
}

/**
 * @title Voting Contract
 * @notice Handles the logic for a single voting event with hybrid access control.
 */
enum VotingType { SingleChoice, MultipleChoice }

contract Voting {
    // --- EVENTS ---
    event VotingInitialized(address indexed organizer, string title, uint256 startTime, uint256 endTime);
    event VoteCast(address indexed voter, uint256[] options, uint256 timestamp);
    event VotingClosed(uint256 timestamp);
    event WhitelistUpdated(address indexed voter, bool status);
    event OrganizerChanged(address indexed oldOrganizer, address indexed newOrganizer);
    event RegistryAdded(address indexed registry);
    event RegistryRemoved(address indexed registry);
    event WhitelistEnabled(uint256 timestamp);
    event VotingTimeUpdated(uint256 newStartTime, uint256 newEndTime);

    // --- STATE VARIABLES ---
    address public organizer;
    string public title;
    string[] public options;

    mapping(address => bool) public hasVoted;
    mapping(uint256 => uint256) public voteCounts;

    uint256 public startTime;
    uint256 public endTime;
    bool public isClosed;
    VotingType public votingType;

    // --- ACCESS CONTROL STATE ---
    bool public useWhitelist;
    mapping(address => bool) public internalWhitelist;
    IWhitelistRegistry[] public registries;

    modifier onlyOrganizer() {
        require(msg.sender == organizer, "Caller is not the organizer");
        _;
    }

    /**
     * @notice Initializes a new voting contract.
     * @param _title Poll title.
     * @param _options List of voting options.
     * @param _startTime Timestamp for voting start (0 for immediate).
     * @param _endTime Timestamp for voting end (0 for indefinite).
     * @param _useWhitelist Enable restricted access mode.
     * @param _votingType Single (0) or Multiple (1) choice.
     * @param _organizer Address of the poll creator.
     */
    constructor(
        string memory _title,
        string[] memory _options,
        uint256 _startTime,
        uint256 _endTime,
        bool _useWhitelist,
        VotingType _votingType,
        address _organizer
    ) {
        organizer = _organizer;
        title = _title;
        options = _options;
        startTime = _startTime;
        endTime = _endTime;
        useWhitelist = _useWhitelist;
        votingType = _votingType;

        emit VotingInitialized(_organizer, _title, _startTime, _endTime);

        if (_useWhitelist) {
            emit WhitelistEnabled(block.timestamp);
        }
    }

    /**
     * @notice Casts a vote for selected options.
     * @param _optionIndices Array of option indices to vote for.
     */
    function vote(uint256[] calldata _optionIndices) public {
        require(_optionIndices.length > 0, "Select at least one option");
        require(!hasVoted[msg.sender], "Already voted");
        require(!isClosed, "Voting is closed");
        require(
            (startTime == 0 || block.timestamp >= startTime) &&
            (endTime == 0 || block.timestamp <= endTime),
            "Voting is not active within the time period"
        );

        // Hybrid Access Control Logic
        if (useWhitelist) {
            bool isAllowed = false;

            // 1. Check Internal Whitelist
            if (internalWhitelist[msg.sender]) {
                isAllowed = true;
            }
            // 2. Check External Registries
            else if (registries.length > 0) {
                for (uint256 i = 0; i < registries.length; i++) {
                    try registries[i].isWhitelisted(msg.sender) returns (bool result) {
                        if (result) {
                            isAllowed = true;
                            break;
                        }
                    } catch {
                        // Ignore failed external calls to prevent DoS
                        continue;
                    }
                }
            }

            require(isAllowed, "Not authorized to vote");
        }

        // Record Vote
        if (votingType == VotingType.SingleChoice) {
            require(_optionIndices.length == 1, "Single choice requires exactly one selection");
            uint256 choice = _optionIndices[0];
            require(choice < options.length, "Invalid option index");
            voteCounts[choice]++;
        } else {
            bool[] memory seen = new bool[](options.length);
            for (uint256 i = 0; i < _optionIndices.length; i++) {
                uint256 idx = _optionIndices[i];
                require(idx < options.length, "Invalid option index");
                require(!seen[idx], "Duplicate selection in one vote");
                seen[idx] = true;
                voteCounts[idx]++;
            }
        }

        hasVoted[msg.sender] = true;
        emit VoteCast(msg.sender, _optionIndices, block.timestamp);
    }

    // --- MANAGEMENT & CONFIGURATION ---

    /**
     * @notice Permanently enables the whitelist mode.
     */
    function enableWhitelist() public onlyOrganizer {
        require(!useWhitelist, "Whitelist is already enabled");
        useWhitelist = true;
        emit WhitelistEnabled(block.timestamp);
    }

    /**
     * @notice Updates the start and end time of the voting.
     * @param _newStartTime New start timestamp (0 for immediate).
     * @param _newEndTime New end timestamp (0 for indefinite).
     */
    function updateVotingPeriod(uint256 _newStartTime, uint256 _newEndTime) public onlyOrganizer {
        require(!isClosed, "Voting is already closed");

        if (_newEndTime != 0) {
            require(_newEndTime > _newStartTime, "End time must be after start time");
            require(_newEndTime > block.timestamp, "End time must be in the future");
        }

        startTime = _newStartTime;
        endTime = _newEndTime;

        emit VotingTimeUpdated(_newStartTime, _newEndTime);
    }

    /**
     * @notice Adds an external registry contract.
     * @dev Automatically enables whitelist mode if not already enabled.
     * @param _registry Address of the IWhitelistRegistry contract.
     */
    function addRegistry(address _registry) public onlyOrganizer {
        require(_registry != address(0), "Invalid registry address");

        if (!useWhitelist) {
            enableWhitelist();
        }

        registries.push(IWhitelistRegistry(_registry));
        emit RegistryAdded(_registry);
    }

    /**
     * @notice Removes an external registry by index.
     * @param _index Index of the registry in the 'registries' array.
     */
    function removeRegistry(uint256 _index) public onlyOrganizer {
        require(_index < registries.length, "Invalid registry index");

        address removedRegistry = address(registries[_index]);

        // Move the last element to the deleted spot (swap-and-pop)
        registries[_index] = registries[registries.length - 1];
        registries.pop();

        emit RegistryRemoved(removedRegistry);
    }

    /**
     * @notice Transfers ownership of the poll.
     * @param _newOrganizer Address of the new organizer.
     */
    function changeOrganizer(address _newOrganizer) public onlyOrganizer {
        require(_newOrganizer != address(0), "Invalid address");
        organizer = _newOrganizer;
        emit OrganizerChanged(organizer, _newOrganizer);
    }

    /**
     * @notice Adds a single voter to the internal whitelist.
     * @dev Automatically enables whitelist mode.
     */
    function addToWhitelist(address _voter) public onlyOrganizer {
        if (!useWhitelist) {
            enableWhitelist();
        }
        internalWhitelist[_voter] = true;
        emit WhitelistUpdated(_voter, true);
    }

    /**
     * @notice Adds multiple voters to the internal whitelist.
     * @dev Automatically enables whitelist mode.
     */
    function addManyToWhitelist(address[] calldata _voters) public onlyOrganizer {
        if (!useWhitelist) {
            enableWhitelist();
        }

        for (uint256 i = 0; i < _voters.length; i++) {
            internalWhitelist[_voters[i]] = true;
            emit WhitelistUpdated(_voters[i], true);
        }
    }

    /**
     * @notice Removes a single voter from the internal whitelist.
     */
    function removeFromWhitelist(address _voter) public onlyOrganizer {
        internalWhitelist[_voter] = false;
        emit WhitelistUpdated(_voter, false);
    }

    /**
     * @notice Removes multiple voters from the internal whitelist.
     */
    function removeManyFromWhitelist(address[] calldata _voters) public onlyOrganizer {
        for (uint256 i = 0; i < _voters.length; i++) {
            internalWhitelist[_voters[i]] = false;
            emit WhitelistUpdated(_voters[i], false);
        }
    }

    /**
     * @notice Irreversibly closes the voting.
     */
    function closeVoting() public onlyOrganizer {
        require(!isClosed, "Voting is already closed");
        isClosed = true;
        emit VotingClosed(block.timestamp);
    }

    // --- GETTERS ---

    /**
     * @notice Returns current vote counts for all options.
     */
    function getResults() public view returns (uint256[] memory) {
        uint256[] memory results = new uint256[](options.length);
        for (uint256 i = 0; i < options.length; i++) {
            results[i] = voteCounts[i];
        }
        return results;
    }

    /**
     * @notice Returns the list of options.
     */
    function getOptions() public view returns (string[] memory) {
        return options;
    }

    /**
     * @notice Returns the list of connected external registries.
     */
    function getRegistries() public view returns (IWhitelistRegistry[] memory) {
        return registries;
    }

    /**
     * @notice Checks if a specific user is allowed to vote.
     * @dev Checks internal whitelist first, then iterates through external registries.
     * @param _user Address to check.
     * @return True if allowed.
     */
    function checkAccess(address _user) public view returns (bool) {
        if (!useWhitelist) return true;

        if (internalWhitelist[_user]) return true;

        for (uint256 i = 0; i < registries.length; i++) {
            try registries[i].isWhitelisted(_user) returns (bool res) {
                if (res) return true;
            } catch {
                continue;
            }
        }

        return false;
    }
}

/**
 * @title VotingFactory
 * @notice Factory contract to deploy new Voting instances using standard deployment.
 */
contract VotingFactory {
    event PollCreated(address indexed poll, string title);
    Voting[] public deployedVotings;

    /**
     * @notice Deploys a new Voting contract.
     * @param _title Title of the poll.
     * @param _options Array of options.
     * @param _startTime Start timestamp.
     * @param _endTime End timestamp.
     * @param _useWhitelist Initial whitelist status.
     * @param _votingType 0 for SingleChoice, 1 for MultipleChoice.
     */
    function createVoting(
        string calldata _title,
        string[] calldata _options,
        uint256 _startTime,
        uint256 _endTime,
        bool _useWhitelist,
        VotingType _votingType
    ) public {
        Voting newVoting = new Voting(
            _title,
            _options,
            _startTime,
            _endTime,
            _useWhitelist,
            _votingType,
            msg.sender
        );
        deployedVotings.push(newVoting);
        emit PollCreated(address(newVoting), _title);
    }

    /**
     * @notice Returns all voting contracts deployed by this factory.
     */
    function getDeployedVotings() public view returns (Voting[] memory) {
        return deployedVotings;
    }
}