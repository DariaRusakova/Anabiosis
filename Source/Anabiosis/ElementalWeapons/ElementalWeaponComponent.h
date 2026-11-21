#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "WeaponMotionState.h"
#include "ElementalWeaponComponent.generated.h"

class AElementalFirstPersonCharacter;
class UElementalWeaponDefinition;
class UEnhancedInputComponent;
class UEnhancedInputLocalPlayerSubsystem;
class UInputAction;
class UInputMappingContext;
class USceneComponent;
class UStaticMeshComponent;
class UAnimSequence;
class UStaticMesh;

struct FElementalArmTargets
{
    UAnimSequence* Pose = nullptr;
    FVector RightHand = FVector::ZeroVector, LeftHand = FVector::ZeroVector;
    FVector RightElbow = FVector::ZeroVector, LeftElbow = FVector::ZeroVector;
    FRotator WristRotation = FRotator::ZeroRotator;
    bool Valid = false;
};

UCLASS(ClassGroup=(Weapons), meta=(BlueprintSpawnableComponent))
class ANABIOSIS_API UElementalWeaponComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UElementalWeaponComponent();
    void BindInputs(UInputComponent* Input);
    void ReleaseInput();
    bool IsReady() const;
    FElementalArmTargets GetArmTargets() const;
protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
private:
    UPROPERTY(Transient) TObjectPtr<AElementalFirstPersonCharacter> Character;
    UPROPERTY(Transient) TObjectPtr<USceneComponent> WeaponRoot;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> WeaponMesh;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> StreamMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> StreamShape;
    UPROPERTY(Transient) TObjectPtr<UInputMappingContext> Mapping;
    UPROPERTY(Transient) TObjectPtr<UInputAction> FireAction;
    UPROPERTY(Transient) TObjectPtr<UInputAction> AimAction;
    UPROPERTY(Transient) TObjectPtr<UInputAction> FlameAction;
    UPROPERTY(Transient) TObjectPtr<UInputAction> WaterAction;
    TWeakObjectPtr<UEnhancedInputLocalPlayerSubsystem> InputSubsystem;
    TWeakObjectPtr<UEnhancedInputComponent> BoundInput;
    TArray<uint32> BindingHandles;
    AnabiosisWeapons::MotionState Motion;
    AnabiosisWeapons::MotionFrame Frame;
    FRotator PreviousLook = FRotator::ZeroRotator;
    float HipFOV = 75;
    bool bTrigger = false, bAiming = false, bHaveLook = false;
    int32 QueuedWeapon = -1;
    void StartFire();
    void StopFire();
    void StartAim();
    void StopAim();
    void SelectFlame();
    void SelectWater();
    void ApplyWeapon();
    void UpdateStream();
    UElementalWeaponDefinition* Definition() const;
};
