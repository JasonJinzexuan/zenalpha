package com.zenalpha.data.service;

import com.zenalpha.common.exception.ZenAlphaException;
import com.zenalpha.data.entity.InstrumentEntity;
import com.zenalpha.data.repository.InstrumentRepository;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class InstrumentService {

    private final InstrumentRepository instrumentRepository;

    public InstrumentService(InstrumentRepository instrumentRepository) {
        this.instrumentRepository = instrumentRepository;
    }

    public List<InstrumentEntity> list() {
        return instrumentRepository.findAllByActiveTrue();
    }

    public InstrumentEntity get(Long id) {
        return instrumentRepository.findById(id)
                .orElseThrow(() -> new ZenAlphaException("INST_001", "Instrument not found: " + id));
    }

    public InstrumentEntity getBySymbol(String symbol) {
        return instrumentRepository.findBySymbol(symbol)
                .orElseThrow(() -> new ZenAlphaException("INST_002", "Instrument not found: " + symbol));
    }

    @Transactional
    public InstrumentEntity create(InstrumentEntity instrument) {
        if (instrumentRepository.findBySymbol(instrument.getSymbol()).isPresent()) {
            throw new ZenAlphaException("INST_003", "Instrument already exists: " + instrument.getSymbol());
        }
        instrument.setCreatedAt(LocalDateTime.now());
        instrument.setActive(true);
        return instrumentRepository.save(instrument);
    }

    @Transactional
    public InstrumentEntity update(Long id, InstrumentEntity update) {
        InstrumentEntity existing = get(id);
        InstrumentEntity updated = new InstrumentEntity();
        updated.setId(existing.getId());
        updated.setSymbol(update.getSymbol() != null ? update.getSymbol() : existing.getSymbol());
        updated.setName(update.getName() != null ? update.getName() : existing.getName());
        updated.setExchange(update.getExchange() != null ? update.getExchange() : existing.getExchange());
        updated.setAssetType(update.getAssetType() != null ? update.getAssetType() : existing.getAssetType());
        updated.setActive(update.isActive());
        updated.setCreatedAt(existing.getCreatedAt());
        return instrumentRepository.save(updated);
    }
}
